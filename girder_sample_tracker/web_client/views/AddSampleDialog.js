import AddSampleDialogTemplate from '../templates/addSampleDialog.pug';
import SampleCreationPolicyModel from '../models/SampleCreationPolicyModel';
import SampleModel from '../models/SampleModel';
import '../stylesheets/addSampleDialog.styl';

const router = girder.router;
const View = girder.views.View;
const AccessWidget = girder.views.widgets.AccessWidget;
const { handleClose, handleOpen } = girder.dialog;

import '@girder/core/utilities/jquery/girderModal';
import 'bootstrap-tagsinput';
import 'bootstrap-tagsinput/dist/bootstrap-tagsinput.css';


var AddSampleDialog = View.extend({
    events: {
        'submit #g-sample-form': function (e) {
            e.preventDefault();
            var eventTypes = this.$('input#eventTypes').val().trim().split(',');
            if (eventTypes.length === 1 && eventTypes[0] === '') {
                eventTypes = [];
            }
            const params = {
                'name': this.$('input#name').val().trim(),
                'description': this.$('input#description').val().trim(),
                'eventTypes': JSON.stringify(eventTypes),
                'access': this.accessWidget ? JSON.stringify(this.accessWidget.getAccessList()) : null
            };
            let batchSize = this.$('input#batchSize').val()
            if (batchSize !== undefined && batchSize !== null && batchSize.trim() !== '') {
                params['batchSize'] = batchSize;
            }
            if (this.sample !== undefined && this.sample !== null) {
                this.sample.set(params).on('g:saved', function () {
                    router.navigate('sample/' + this.id, {trigger: true});
                }).save();
            } else {
                const sample = new SampleModel(params).on('g:saved', function () {
                    router.navigate('sample/' + sample.responseJSON._id, {trigger: true});
                }, this).on('g:error', function (err) {
                    this.$('.g-validation-failed-message').text(err.responseJSON.message);
                    this.$('button#g-add-sample-btn').girderEnable(true);
                }, this).save();
            }
        }
    },

    initialize: function (settings) {
        this.sample = settings.parentView.model;
        this.isNew = this.sample === undefined || this.sample === null;
    },

    render: function () {
        this.$el.html(AddSampleDialogTemplate({isNew: this.isNew})).girderModal(this)
            .on('shown.bs.modal', () => {
                this.$('#g-name').focus();
            }).on('hidden.bs.modal', () => {
                handleClose('addSample', {replace: true});
            });
        handleOpen('addSample', {replace: true});
        $('input#eventTypes').tagsinput();
        if (this.sample !== undefined && this.sample !== null) {
            this.$('input#name').val(this.sample.get('name') || null);
            this.$('input#description').val(this.sample.get('description') || null);
            const tags = this.sample.get('eventTypes') || [];
            tags.forEach((tag) => {
                $('input#eventTypes').tagsinput('add', tag);
            });
        } else { // Only show access widget if creating a new sample
            var sampleModel = new SampleCreationPolicyModel();
            this.accessWidget = new AccessWidget({
                el: this.$('.access-widget-container'),
                parentView: this,
                modelType: 'sample',
                model: sampleModel,
                modal: false,
                hideRecurseOption: true,
                hideSaveButton: true,
                hidePrivacyEditor: true,
                hideAccessType: false,
                noAccessFlag: true
            });
        }
        this.$('input#name').focus();

        return this;
    }
});

export default AddSampleDialog;
