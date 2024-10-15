import router from 'girder/router';
import View from 'girder/views/View';
import PaginateWidget from 'girder/views/widgets/PaginateWidget';
import { getCurrentUser } from 'girder/auth';
import { AccessType } from 'girder/constants';
import { confirm } from 'girder/dialog';
import { formatDate, DATE_DAY } from 'girder/misc';
import { restRequest, getApiRoot } from 'girder/rest';

import SampleCollection from '../collections/SampleCollection';
import SampleListTemplate from '../templates/sampleList.pug';
import CheckedMenuWidget from './CheckedMenuWidget';
import AddSampleDialog from './AddSampleDialog';

import '../stylesheets/sampleList.styl';

var SampleListView = View.extend({
    events: {
        'click .g-new-sample': function (event) {
            event.preventDefault();
            new AddSampleDialog({
                el: $('#g-dialog-container'),
                parentView: this
            }).render();
        },
        'click .g-view-sample': function (event) {
            const sampleId = this.collection.get($(event.currentTarget).attr('cid')).id;
            router.navigate(`sample/${sampleId}`, {trigger: true});
        },
        'change .g-select-all': function (event) {
            this.$('.g-select-sample').prop('checked', event.currentTarget.checked);
            this.updateChecked();
        },
        'click .g-select-sample': function (event) {
            var checkbox = $(event.currentTarget);
            this.updateChecked();
        },
        'click a.g-delete-checked': 'deleteCheckedDialog',
        'click a.g-download-checked': 'downloadChecked',
    },

    initialize: function (settings) {
        this.parentView = settings.parentView;
        this.parentModel = settings.parentModel;
        this.checked = [];
        this.collection = new SampleCollection();
        this.collection.on('g:changed', function () {
            this.render();
        }, this).fetch({}, true);
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

    updateChecked: function () {
        this.recomputeChecked();
        var samples = this.checked;

        var minSampleLevel = AccessType.ADMIN;
        _.every(samples, function (cid) {
            var sample = this.collection.get(cid);
            minSampleLevel = Math.min(minSampleLevel, sample.getAccessLevel());
            return minSampleLevel > AccessType.READ;
        }, this);

        console.log('minSampleLevel', minSampleLevel);

        let anyChecked = samples.length > 0;
        this.checkedMenuWidget.update({
            minSampleLevel: minSampleLevel,
            pickedCount: samples.length,
        });
    },

    _getCheckedSampleIds: function () {
        return _.map(this.checked, function (cid) {
            return this.collection.get(cid).id;
        }, this);
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
        console.log('redirectViaForm', method, url, data);
        var form = $('<form>').attr({action: url, method: method});
        _.each(data, function (value, key) {
            form.append($('<input/>').attr({type: 'text', name: key, value: value}));
        });
        $(form).appendTo('body').submit().remove();
    },

    downloadChecked: function () {
        console.log('downloadChecked');
        var url = getApiRoot() + '/sample/download';
        this.redirectViaForm('POST', url, {
            ids: JSON.stringify(this._getCheckedSampleIds())
        });
    }
});

export default SampleListView;
