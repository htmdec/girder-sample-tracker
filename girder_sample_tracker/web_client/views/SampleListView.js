import $ from 'jquery';
import _ from 'underscore';

import SampleCollection, { PAGE_SIZES } from '../collections/SampleCollection';
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
const { restRequest } = girder.rest;


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
            const checked = event.currentTarget.checked;
            this.$('.g-select-sample').prop('checked', checked);
            // This page only. The collection holds the page on screen, and a
            // row the user cannot see is not one they just ticked.
            this.collection.each((sample) => this._remember(sample, checked));
            this.updateChecked();
        },
        'change .g-select-sample': function (event) {
            const checkbox = $(event.currentTarget);
            this._remember(
                this.collection.get(checkbox.attr('g-sample-cid')),
                checkbox.prop('checked')
            );
            this._syncSelectAll();
            this.updateChecked();
        },
        'change select.g-page-size': function (event) {
            this.collection.setPageLimit(parseInt($(event.currentTarget).val(), 10));
            this.collection.fetch({}, true);
        },
        'click a.g-delete-checked': 'deleteCheckedDialog',
        'click a.g-access-checked': 'accessCheckedDialog',
        'click a.g-download-checked': 'downloadChecked',
        'click a.g-clear-checked': 'clearChecked',
        'input .g-filter-field': 'search'
    },

    initialize: function (settings) {
        this.pending = null;
        this.parentView = settings.parentView;
        this.parentModel = settings.parentModel;
        // The selection, as sample id -> model. Held here rather than read
        // back off the checkboxes, because a fetch replaces every row: a
        // selection spanning more than one page -- which is the only way to
        // pick more samples than fit on one -- has nothing in the DOM to be
        // recovered from once the user turns the page. The models come along
        // because the checked-actions menu needs their access level, and the
        // collection only ever holds the page on screen.
        this.checkedSamples = {};
        this.downloading = false;
        this.collection = new SampleCollection();
        // Before the first fetch, so the page opens at the size last chosen.
        this.collection.updateFromSession();
        // Bound once. Re-registering this per search leaked a handler each
        // time, so the Nth search re-rendered the whole list N times.
        this.listenTo(this.collection, 'g:changed', this._renderData);
        this.collection.fetch({});
        this.paginateWidget = new PaginateWidget({
            collection: this.collection,
            parentView: this
        });
        this.checkedMenuWidget = new CheckedMenuWidget({
            pickedCount: 0,
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
            user: getCurrentUser(),
            pageSize: this.collection.pageLimit,
            pageSizes: PAGE_SIZES
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

        this._restoreCheckboxes();
        this.updateChecked();
        return this;
    },

    updateChecked: function () {
        var samples = _.values(this.checkedSamples);

        var minSampleLevel = AccessType.ADMIN;
        _.every(samples, function (sample) {
            minSampleLevel = Math.min(minSampleLevel, sample.getAccessLevel());
            return minSampleLevel > AccessType.READ;
        });

        this.checkedMenuWidget.update({
            minSampleLevel: minSampleLevel,
            pickedCount: samples.length
        });
    },

    /** Add or drop one sample from the selection. */
    _remember: function (sample, checked) {
        if (!sample) {
            return;
        }
        if (checked) {
            this.checkedSamples[sample.id] = sample;
        } else {
            delete this.checkedSamples[sample.id];
        }
    },

    _getCheckedSampleIds: function () {
        return _.keys(this.checkedSamples);
    },

    /** Tick the rows of this page that are part of the selection. */
    _restoreCheckboxes: function () {
        _.each(this.$('.g-select-sample'), function (checkbox) {
            var sample = this.collection.get($(checkbox).attr('g-sample-cid'));
            $(checkbox).prop('checked', !!sample && sample.id in this.checkedSamples);
        }, this);
        this._syncSelectAll();
    },

    /**
     * The select-all box reflects this page, not the whole selection: it is
     * the control for the rows under it, and ticking it with a hundred
     * samples already picked elsewhere should not look like it undid them.
     */
    _syncSelectAll: function () {
        this.$('.g-select-all').prop(
            'checked',
            !this.collection.isEmpty() &&
                this.$('.g-select-sample:not(:checked)').length === 0
        );
    },

    clearChecked: function () {
        this.checkedSamples = {};
        this.$('.g-select-sample,.g-select-all').prop('checked', false);
        this.updateChecked();
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
                    this.clearChecked();
                    this.collection.fetch({}, true);
                });
            }
        };
        confirm(params);
    },

    accessCheckedDialog: function () {
        var samples = this._getCheckedSampleIds();
        var sample = this.checkedSamples[samples[0]];
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
        const ids = this._getCheckedSampleIds();
        // One QR code is ~36ms of rendering on the server, so a selection of
        // a few hundred is tens of seconds during which the menu is still
        // there to be clicked again.
        if (this.downloading || !ids.length) {
            return;
        }
        this.downloading = true;
        events.trigger('g:alert', {
            icon: 'download',
            text: `Preparing QR codes for ${ids.length} sample(s)...`,
            type: 'info',
            timeout: 4000
        });

        restRequest({
            url: 'sample/download',
            method: 'POST',
            // The ids are the request body, not a query parameter: a
            // selection gathered across several pages outgrows what a query
            // string can be relied on to carry.
            contentType: 'application/json',
            processData: false,
            data: JSON.stringify(ids),
            // Without this the transport hands back a string and the zip is
            // mangled on the way through.
            xhrFields: {responseType: 'blob'},
            // Handled below, where the message can be read out of the blob.
            error: null
        }).done((blob) => {
            this._saveBlob(blob, 'samples.zip');
        }).fail((xhr) => {
            this._downloadFailed(xhr);
        }).always(() => {
            this.downloading = false;
        });
    },

    /** Hand a blob to the browser as a file to save. */
    _saveBlob: function (blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        // Not before the click has been dispatched, or the browser is handed
        // a url that no longer resolves to anything.
        window.setTimeout(() => window.URL.revokeObjectURL(url), 0);
    },

    _downloadFailed: function (xhr) {
        const alert = (text) => events.trigger('g:alert', {
            icon: 'cancel',
            text: text || 'Could not download the QR codes.',
            type: 'danger',
            timeout: 5000
        });
        // The response is a blob, because that is what the transport was
        // asked for, so the server's explanation of a 400 has to be read back
        // out of it rather than picked off responseJSON.
        if (xhr.response instanceof Blob) {
            xhr.response.text().then(
                (body) => {
                    let message = null;
                    try {
                        message = JSON.parse(body).message;
                    } catch (e) {
                        message = null;
                    }
                    alert(message);
                },
                () => alert(null)
            );
        } else {
            alert(null);
        }
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
