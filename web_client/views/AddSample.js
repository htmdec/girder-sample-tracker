import $ from 'jquery';

import router from 'girder/router';
import View from 'girder/views/View';
import { handleClose, handleOpen } from 'girder/dialog';

import AddSampleDialogTemplate from '../templates/addSampleDialog.pug';
import SampleModel from '../models/SampleModel';

import 'girder/utilities/jquery/girderModal';

var AddSampleView = View.extend({
    events: {
        'submit #g-sample-form': function (e) {
            e.preventDefault();
            const data = $(e.currentTarget).serializeArray();
            const params = new Map(data.map((obj) => [obj.name, obj.value]));
            const sample = new SampleModel(Object.fromEntries(params)).on('g:saved', function () {
            }).on('g:saved', function () {
                router.navigate('sample/' + sample.responseJSON._id, {trigger: true});
            }, this).save();
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
        this.$('#g-name').focus();
        return this;
    }
});

export default AddSampleView;
