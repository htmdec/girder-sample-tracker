import $ from 'jquery';

import router from 'girder/router';
import View from 'girder/views/View';
import { handleClose, handleOpen } from 'girder/dialog';
import { restRequest } from 'girder/rest';

import AddEventDialogTemplate from '../templates/addEventDialog.pug';

import 'girder/utilities/jquery/girderEnable';
import 'girder/utilities/jquery/girderModal';

var AddEventView = View.extend({
    events: {
        'submit #g-event-form': function (e) {
            e.preventDefault();
            const data = $(e.currentTarget).serializeArray();
            const params = new Map(data.map((obj) => [obj.name, obj.value]));
            restRequest({
                type: 'POST',
                url: 'sample/' + this.sample.get('_id') + '/event',
                data: Object.fromEntries(params)
            }).done(() => {
                this.$el.modal('hide');
                router.navigate('sample/' + this.sample.get('_id'), {trigger: true});
            });
        }
    },

    initialize: function (settings) {
        this.sample = settings.parentView.model;
    },

    geoLocation: function () {
        const locationField = document.querySelector('input#location');
        function success(position) {
            const latitude  = position.coords.latitude;
            const longitude = position.coords.longitude;
            locationField.value = latitude + ',' + longitude;
            locationField.href = 'https://www.openstreetmap.org/#map=18/' + latitude + '/' + longitude;
        }

        function error() {
            locationField.value = 'Unable to retrieve your location';
        }

        if (!navigator.geolocation) {
            locationField.value = 'Geolocation is not supported by your browser';
        } else {
            locationField.value = 'Locating…';
            navigator.geolocation.getCurrentPosition(success, error);
        }
    },

    render: function () {
        this.$el.html(AddEventDialogTemplate({
            sample: this.sample
        })).girderModal(this)
            .on('shown.bs.modal', () => {
                this.geoLocation();
                this.$('#g-name').focus();
            }).on('hidden.bs.modal', () => {
                handleClose('addEvent', {replace: true});
            });
        handleOpen('addEvent', {replace: true});
        this.$('#g-name').focus();
        return this;
    }
});

export default AddEventView;
