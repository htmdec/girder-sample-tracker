// Extends and overrides API
import { wrap } from 'girder/utilities/PluginUtils';

import GlobalNavView from 'girder/views/layout/GlobalNavView';

import './routes';

wrap(GlobalNavView, 'initialize', function (initialize) {
    initialize.apply(this, arguments);

    this.defaultNavItems.push({
        name: 'Sample Tracker',
        icon: 'icon-compass',
        target: 'samples'
    });
});
