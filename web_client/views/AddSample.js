import $ from 'jquery';

import router from 'girder/router';
import View from 'girder/views/View';
import { handleClose, handleOpen } from 'girder/dialog';

import AddSampleDialogTemplate from '../templates/addSampleDialog.pug';
import SampleModel from '../models/SampleModel';
import '../stylesheets/addSampleDialog.styl';

import 'girder/utilities/jquery/girderModal';
import 'bootstrap-tagsinput';
import 'bootstrap-tagsinput/dist/bootstrap-tagsinput.css';

var AddSampleView = View.extend({
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
                'eventTypes': JSON.stringify(eventTypes)
            };
            if (this.sample !== undefined && this.sample !== null) {
                this.sample.set(params).on('g:saved', function () {
                    router.navigate('sample/' + this.id, {trigger: true});
                }).save();
            } else {
                const sample = new SampleModel(params).on('g:saved', function () {
                    router.navigate('sample/' + sample.responseJSON._id, {trigger: true});
                }, this).save();
            }
        }
    },

    initialize: function (settings) {
        this.sample = settings.parentView.model;
    },

    render: function () {
        this.$el.html(AddSampleDialogTemplate({})).girderModal(this)
            .on('shown.bs.modal', () => {
                this.$('#g-name').focus();
            }).on('hidden.bs.modal', () => {
                handleClose('addSample', {replace: true});
            });
        handleOpen('addSample', {replace: true});
        this.$('input#eventTypes').tagsinput();
        if (this.sample !== null) {
            this.$('input#name').val(this.sample.get('name') || null);
            this.$('input#description').val(this.sample.get('description') || null);
            const tags = this.sample.get('eventTypes') || [];
            tags.forEach((tag) => {
                this.$('input#eventTypes').tagsinput('add', tag);
            });
        }
        this.$('input#name').focus();

        return this;
    }
});

export default AddSampleView;
