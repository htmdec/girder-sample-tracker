import router from 'girder/router';
import events from 'girder/events';

import SampleListView from './views/SampleListView';
import SampleView from './views/SampleView';
import SampleModel from './models/SampleModel';

router.route('samples', 'samples', function () {
    events.trigger('g:navigateTo', SampleListView);
});

router.route('sample/:id', 'sample', function (id, params) {
    const sample = new SampleModel({_id: id});
    sample.fetch().done(() => {
        events.trigger('g:navigateTo', SampleView, {
            model: sample,
            addEvent: params.dialog === 'addEvent'
        }, {
            renderNow: true
        });
    }).fail(() => {
        router.navigate('samples', {trigger: true, replace: true});
    });
});
