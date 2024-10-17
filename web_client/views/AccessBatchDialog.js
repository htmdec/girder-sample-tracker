import View from 'girder/views/View';

import { handleClose, handleOpen } from 'girder/dialog';
import { restRequest } from 'girder/rest';
import AccessWidget from 'girder/views/widgets/AccessWidget';

import AccessBatchDialogTemplate from '../templates/accessBatchDialog.pug';

var AccessBatchDialog = View.extend({
    events: {
        'submit #g-batch-samples-form': function (e) {
            e.preventDefault();
            var acList = this.accessWidget.getAccessList();
            restRequest({
                url: 'sample/access',
                method: 'PUT',
                data: {
                    ids: JSON.stringify(this.samples),
                    access: JSON.stringify(acList)
                }
            }).done(() => {
                this.$el.modal('hide');
                this.parentView.collection.fetch({}, true);
            });
        }
    },

    initialize: function (settings) {
        this.model = settings.model;
        this.parentView = settings.parentView;
        this.samples = settings.samples;
    },

    render: function () {
        this.$el.html(AccessBatchDialogTemplate({isNew: this.isNew})).girderModal(this)
            .on('shown.bs.modal', () => {
                this.$('#g-name').focus();
            }).on('hidden.bs.modal', () => {
                handleClose('accessSample', {replace: true});
            });
        handleOpen('accessSample', {replace: true});
        this.accessWidget = new AccessWidget({
            el: this.$('.access-widget-container'),
            parentView: this,
            modelType: 'sample',
            model: this.model,
            modal: false,
            hideRecurseOption: true,
            hideSaveButton: true,
            hidePrivacyEditor: true,
            hideAccessType: false,
            noAccessFlag: true
        });
        this.accessWidget.render();
        return this;
    }
});

export default AccessBatchDialog;
