import $ from 'jquery';
import _ from 'underscore';

import SampleCollection from '../collections/SampleCollection';
import SampleListTemplate from '../templates/sampleList.pug';
import SampleListTableTemplate from '../templates/sampleListTable.pug';
import CheckedMenuWidget from './CheckedMenuWidget';
import AddEventDialog from './AddEventDialog';
import AddSampleDialog from './AddSampleDialog';
import AccessBatchDialog from './AccessBatchDialog';

import '../stylesheets/sampleList.styl';

const router = girder.router;
const View = girder.views.View;
const PaginateWidget = girder.views.widgets.PaginateWidget;
const { getCurrentUser } = girder.auth;
const { AccessType } = girder.constants;
const { confirm } = girder.dialog;
const events = girder.events;
const { formatDate, DATE_DAY } = girder.misc;
const { restRequest, getApiRoot } = girder.rest;


var SampleListView = View.extend({
    events: {
        'click .g-new-sample': function (event) {
            event.preventDefault();
            new AddSampleDialog({
                el: $('#g-dialog-container'),
                parentView: this
            }).render();
        },
        'click .g-add-event': 'addEventChecked',
        'click .g-view-sample': function (event) {
            const sampleId = this.collection.get($(event.currentTarget).attr('cid')).id;
            router.navigate(`sample/${sampleId}`, {trigger: true});
        },
        'change .g-select-all': function (event) {
            this.$('.g-select-sample').prop('checked', event.currentTarget.checked);
            this.updateChecked();
        },
        'click .g-select-sample': function (event) {
            this.updateChecked();
        },
        'click a.g-delete-checked': 'deleteCheckedDialog',
        'click a.g-access-checked': 'accessCheckedDialog',
        'click a.g-download-checked': 'downloadChecked',
        'input .g-filter-field': 'search'
    },

    initialize: function (settings) {
        this.pending = null;
        this.parentView = settings.parentView;
        this.parentModel = settings.parentModel;
        this.checked = [];
        // The ids behind this.checked, kept separately because a fetch resets
        // the collection and every cid with it, and a filter or a page turn
        // should not silently drop what the user had ticked.
        this.checkedIds = [];
        this.collection = new SampleCollection();
        // Bound once. Re-registering this per search leaked a handler each
        // time, so the Nth search re-rendered the whole list N times.
        this.listenTo(this.collection, 'g:changed', this._renderData);
        this.collection.fetch({});
        this.paginateWidget = new PaginateWidget({
            collection: this.collection,
            parentView: this
        });
        this.checkedMenuWidget = new CheckedMenuWidget({
            pickedCount: this.checked.length,
            pickedCopyAllowed: false,
            pickedMoveAllowed: false,
            pickedDesc: '',
            parentView: this
        });
        // The router navigates here without rendering, and the chrome no
        // longer waits on a fetch to draw itself, so put it up now: the
        // filter field is usable while the first page is still in flight.
        this.render();
    },

    render: function () {
        this.$el.html(SampleListTemplate({
            user: getCurrentUser()
        }));
        this._renderData();
        return this;
    },

    /**
     * Redraw only the part of the page that a fetch changes. The chrome above
     * it -- in particular the filter field -- is left alone, so typing is not
     * interrupted by its own results arriving.
     */
    _renderData: function () {
        if (!this.$('.g-main-content').length) {
            // Nothing to fill in yet; render() will call us once there is.
            return this;
        }
        this.$('.g-main-content').html(SampleListTableTemplate({
            samples: this.collection.toArray(),
            formatDate: formatDate,
            DATE_DAY: DATE_DAY
        }));

        const empty = this.collection.isEmpty();
        this.$('.g-main-content,.g-samples-pagination').toggle(!empty);
        this.$('.g-no-samples-record').toggle(empty);

        this.paginateWidget.setElement(this.$('.g-samples-pagination')).render();
        this.checkedMenuWidget.dropdownToggle = this.$('.g-checked-actions-button');
        this.checkedMenuWidget.setElement(this.$('.g-checked-actions-menu')).render();

        this._setCheckboxes(this.checkedIds);
        this.$('.g-select-all').prop(
            'checked',
            !empty && this.$('.g-select-sample:not(:checked)').length === 0
        );
        this.updateChecked();
        return this;
    },

    updateChecked: function (count = true) {
        if (count) {
            this.recomputeChecked();
        }
        var samples = this.checked;

        var minSampleLevel = AccessType.ADMIN;
        _.every(samples, function (cid) {
            var sample = this.collection.get(cid);
            minSampleLevel = Math.min(minSampleLevel, sample.getAccessLevel());
            return minSampleLevel > AccessType.READ;
        }, this);

        // let anyChecked = samples.length > 0;
        this.checkedMenuWidget.update({
            minSampleLevel: minSampleLevel,
            pickedCount: samples.length
        });
    },

    _getCheckedSampleIds: function () {
        return _.map(this.checked, function (cid) {
            return this.collection.get(cid).id;
        }, this);
    },

    _setCheckboxes: function (checked) {
        _.each(this.$('.g-select-sample'), function (checkbox) {
            var sampleId = this.collection.get($(checkbox).attr('g-sample-cid')).id;
            if (checked.includes(sampleId)) {
                $(checkbox).prop('checked', true);
            }
        }
            , this);
    },

    _clearChecked: function () {
        this.checked = [];
        this.updateChecked(false);
    },

    deleteCheckedDialog: function () {
        var params = {
            text: 'Are you sure you want to delete the selected samples?',
            escapedHtml: true,
            yesText: 'Delete',
            confirmCallback: () => {
                restRequest({
                    url: 'sample',
                    method: 'DELETE',
                    data: {ids: JSON.stringify(this._getCheckedSampleIds())},
                    headers: {'X-HTTP-Method-Override': 'DELETE'}
                }).done(() => {
                    this.collection.fetch({}, true);
                });
            }
        };
        confirm(params);
    },

    recomputeChecked: function () {
        this.checked = _.map(this.$('.g-select-sample:checked'), function (checkbox) {
            return $(checkbox).attr('g-sample-cid');
        });
        this.checkedIds = this._getCheckedSampleIds();
    },

    redirectViaForm: function (method, url, data) {
        var form = $('<form>').attr({action: url, method: method});
        _.each(data, function (value, key) {
            form.append($('<input/>').attr({type: 'text', name: key, value: value}));
        });
        $(form).appendTo('body').submit().remove();
    },

    accessCheckedDialog: function () {
        var samples = this._getCheckedSampleIds();
        var sample = this.collection.get(samples[0]);
        new AccessBatchDialog({
            el: $('#g-dialog-container'),
            model: sample,
            modelType: 'sample',
            parentView: this,
            samples: samples
        }, this).render();
    },

    addEventChecked: function () {
        new AddEventDialog({
            el: $('#g-dialog-container'),
            parentView: this
        }).on('g:submit', (params) => {
            const data = Object.fromEntries(params);
            data.ids = JSON.stringify(this._getCheckedSampleIds());
            restRequest({
                type: 'POST',
                url: 'sample/event',
                data: data
            }).done((resp) => {
                if (resp.failed > 0) {
                    events.trigger('g:alert', {
                        icon: 'cancel',
                        text: `${resp.failed} sample(s) failed to receive the event.`,
                        type: 'warning'
                    });
                }
                events.trigger('g:alert', {
                    icon: 'ok',
                    text: `${resp.processed} sample(s) received the event.`,
                    type: 'success'
                });
            });
        });
    },

    downloadChecked: function () {
        var url = getApiRoot() + '/sample/download';
        this.redirectViaForm('POST', url, {
            ids: JSON.stringify(this._getCheckedSampleIds())
        });
    },

    // Brackets go too: what is left is handed to the server as a regex, and
    // an unclosed character class is an error rather than a narrower search.
    _sanitizeRegex: function (q) {
        return q.replaceAll(/[&/\\#,+()$~%.^'":*?<>{}[\]]/g, '');
    },

    search: function () {
        // only search when the user stops typing
        if (this.pending) {
            clearTimeout(this.pending);
        }

        this.pending = setTimeout(() => {
            this.pending = null;
            const q = this.$('.g-filter-field').val();
            // The server matches the name, in one request. Filtering here
            // instead meant walking the whole collection a page at a time --
            // one request per page, however few samples actually matched --
            // and it left the pager counting unfiltered pages.
            this.collection.params = q ? {query: this._sanitizeRegex(q)} : {};
            this.collection.fetch({}, true);
        }, 500);
        return this;
    }

});

export default SampleListView;
