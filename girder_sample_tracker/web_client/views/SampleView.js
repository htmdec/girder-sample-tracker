import SampleTemplate from '../templates/sampleView.pug';
import '../stylesheets/sampleView.styl';
import AddEventDialog from './AddEventDialog';
import AddSampleDialog from './AddSampleDialog';

import QRCode from 'qrcode';

const router = girder.router;
const View = girder.views.View;
const AccessWidget = girder.views.widgets.AccessWidget;
const { formatDate, DATE_MINUTE } = girder.misc;
const { AccessType } = girder.constants;

const QRparams = {
  'errorCorrectionLevel': 'H',
  'version': 6,
  'mode': 'alphanumeric',
}


var SampleView = View.extend({
    events: {
        'click .g-new-event': function (event) {
            this.addEventDialog();
        },
        'click .g-edit-access': 'editAccess',
        'click .g-delete-sample': 'destroySample',
        'click .g-download-sample': function () {
            this.model.download();
        },
        'click .g-edit-sample': function () {
            event.preventDefault();
            new AddSampleDialog({
                el: $('#g-dialog-container'),
                parentView: this
            }).render();
        }
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
            AccessType: AccessType,
            level: this.model.getAccessLevel(),
            formatDate: formatDate,
            DATE_MINUTE: DATE_MINUTE
        }));
        const addEventUrl = `${window.location.origin}/#sample/${this.model.id}/add`;
        QRCode.toCanvas(this.$('#g-sample-qr')[0], addEventUrl.toUpperCase(), QRparams);
        if (this.addEvent) {
            this.addEventDialog();
        }
        return this;
    },

    addEventDialog: function () {
        new AddEventDialog({
            el: $('#g-dialog-container'),
            parentView: this
        }).render();
    },

    editAccess: function () {
        new AccessWidget({
            el: $('#g-dialog-container'),
            model: this.model,
            modelType: 'sample',
            parentView: this,
            hideRecurseOption: true,
            hidePrivacyEditor: true,
            hideAccessType: false,
            noAccessFlag: true
        }, this).render();
    }
});

export default SampleView;
