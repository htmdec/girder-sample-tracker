import SampleModel from '../models/SampleModel';

const Collection = girder.collections.Collection;

var SampleCollection = Collection.extend({
    resourceName: 'sample',
    model: SampleModel,
    pageLimit: 50
});

export default SampleCollection;
