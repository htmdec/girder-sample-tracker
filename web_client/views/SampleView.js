import QRCode from 'qrcode';
import router from 'girder/router';
import View from 'girder/views/View';
import AccessWidget from 'girder/views/widgets/AccessWidget';
import { formatDate, DATE_MINUTE } from 'girder/misc';

import SampleTemplate from '../templates/sampleView.pug';
import '../stylesheets/sampleView.styl';
import AddEventView from './AddEvent';

var SampleView = View.extend({
    events: {
        'click .g-new-event': function (event) {
            this.addEventDialog();
        },
        'click .g-edit-access': 'editAccess',
        'click .g-delete-sample': 'destroySample'
    },

    initialize: function (settings) {
        // cancelRestRequests('fetch');
        this.addEvent = settings.addEvent;
        this.model = settings.model;
        this.render();
    },

    destroySample: function () {
        this.model.on('g:deleted', function () {
            router.navigate('samples', {trigger: true});
        }).destroy();
    },

    render: function () {
        this.$el.html(SampleTemplate({
            sample: this.model,
            events: this.model.get('events'),
            formatDate: formatDate,
            DATE_MINUTE: DATE_MINUTE
        }));
        const addEventUrl = `${window.location.origin}/#sample/${this.model.id}?dialog=addEvent`;
        console.log(addEventUrl);
        QRCode.toCanvas(this.$('#g-sample-qr')[0], addEventUrl, { errorCorrectionLevel: 'H' });
        if (this.addEvent) {
            this.addEventDialog();
        }
        return this;
    },

    addEventDialog: function () {
        new AddEventView({
            el: $('#g-dialog-container'),
            parentView: this
        }).render();
    },

    editAccess: function () {
        new AccessWidget({
            el: $('#g-dialog-container'),
            model: this.model,
            modelType: 'sample',
            parentView: this
        }, this).render();
    }
});

export default SampleView;
