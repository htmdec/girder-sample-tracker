const router = girder.router;
const View = girder.views.View;
const { handleClose, handleOpen } = girder.dialog;
const { restRequest } = girder.rest;

import AddEventDialogTemplate from '../templates/addEventDialog.pug';
import '@girder/core/utilities/jquery/girderEnable';
import '@girder/core/utilities/jquery/girderModal';

import 'bootstrap/js/dropdown';

var AddEventDialog = View.extend({
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
        this.eventTypes = this.sample.attributes.eventTypes;
        console.log('AddEventDialog initialize');
    },

    geoLocation: function () {
        const locationField = document.querySelector('input#location');
        function success(position) {
            const latitude  = position.coords.latitude;
            const longitude = position.coords.longitude;
            locationField.value = latitude + ',' + longitude;
        }

        function error() {
            locationField.value = 'Unknown';
        }

        if (!navigator.geolocation) {
            locationField.value = 'Unknown';
        } else {
            locationField.value = 'Locating…';
            navigator.geolocation.getCurrentPosition(success, error);
        }
    },

    render: function () {
        this.$el.html(AddEventDialogTemplate({
            sample: this.sample,
            tagsDropdown: this.eventTypes !== undefined ? this.eventTypes.length > 0 : false
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

export default AddEventDialog;
