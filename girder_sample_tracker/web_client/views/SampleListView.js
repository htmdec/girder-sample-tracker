import $ from 'jquery';
import _ from 'underscore';

import SampleCollection from '../collections/SampleCollection';
import SampleListTemplate from '../templates/sampleList.pug';
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
        this.ajaxLock = false;
        this.pending = null;
        this.parentView = settings.parentView;
        this.parentModel = settings.parentModel;
        this.checked = [];
        this.collection = new SampleCollection();
        this.collection.on('g:changed', function () {
            this.render();
        }, this).fetch({});
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
    },

    render: function () {
        this.$el.html(SampleListTemplate({
            samples: this.collection.toArray(),
            formatDate: formatDate,
            DATE_DAY: DATE_DAY,
            user: getCurrentUser()
        }));
        if (this.collection.isEmpty()) {
            this.$('.g-main-content,.g-samples-pagination').hide();
            this.$('.g-no-samples').show();
        } else {
            this.$('.g-main-content,.g-samples-pagination').show();
            this.$('.g-no-samples').hide();
        }
        this.paginateWidget.setElement(this.$('.g-samples-pagination')).render();
        this.checkedMenuWidget.dropdownToggle = this.$('.g-checked-actions-button');
        this.checkedMenuWidget.setElement(this.$('.g-checked-actions-menu')).render();
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

    _sanitizeRegex: function (q) {
        return q.replaceAll(/[&/\\#,+()$~%.^'":*?<>{}]/g, '');
    },

    search: function () {
        // only search when the user stops typing
        if (this.pending) {
            clearTimeout(this.pending);
        }

        this.pending = setTimeout(() => {
            var q = this.$('.g-filter-field').val();
            if (!q) {
                this.collection.filterFunc = null;
            } else {
                let regex = this._sanitizeRegex(q);
                this.collection.filterFunc = function (model) {
                    var match = model.name.match(new RegExp(regex, 'i'));
                    return match;
                };
            }
            const oldChecked = this._getCheckedSampleIds();
            this.collection.on('g:changed', function () {
                this.render();
                this._setCheckboxes(oldChecked);
                this.updateChecked();
                this.$('.g-filter-field').val(q);
                this.$('.g-filter-field').focus();
            }, this).fetch({}, true);
        }, 500);
        return this;
    }

});

export default SampleListView;
