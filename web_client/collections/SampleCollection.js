import Collection from 'girder/collections/Collection';

import SampleModel from '../models/SampleModel';

var SampleCollection = Collection.extend({
    resourceName: 'sample',
    model: SampleModel,
    pageLimit: 50
});

export default SampleCollection;
