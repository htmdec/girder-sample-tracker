// Extends and overrides API
import './routes';

const { wrap } = girder.utilities.PluginUtils;
const GlobalNavView = girder.views.layout.GlobalNavView;

wrap(GlobalNavView, 'initialize', function (initialize) {
    initialize.apply(this, arguments);

    this.defaultNavItems.push({
        name: 'Sample Tracker',
        icon: 'icon-compass',
        target: 'samples'
    });
});
