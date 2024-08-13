import router from 'girder/router';
import View from 'girder/views/View';
import PaginateWidget from 'girder/views/widgets/PaginateWidget';
import { getCurrentUser } from 'girder/auth';
import { formatDate, DATE_DAY } from 'girder/misc';

import SampleCollection from '../collections/SampleCollection';
import SampleListTemplate from '../templates/sampleList.pug';
import AddSampleView from './AddSample';

import '../stylesheets/sampleList.styl';

var SampleListView = View.extend({
    events: {
        'click .g-new-sample': function (event) {
            event.preventDefault();
            new AddSampleView({
                el: $('#g-dialog-container'),
                parentView: this
            }).render();
        },
        'click .g-view-sample': function (event) {
            const sampleId = this.collection.get($(event.currentTarget).attr('cid')).id;
            router.navigate(`sample/${sampleId}`, {trigger: true});
        }
    },

    initialize: function (settings) {
        this.parentView = settings.parentView;
        this.parentModel = settings.parentModel;
        this.collection = new SampleCollection();
        this.collection.on('g:changed', function () {
            this.render();
        }, this).fetch({}, true);
        this.paginateWidget = new PaginateWidget({
            collection: this.collection,
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
        return this;
    }
});

export default SampleListView;
