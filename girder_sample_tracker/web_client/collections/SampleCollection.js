import SampleModel from '../models/SampleModel';

const Collection = girder.collections.Collection;

/** Offered in the list view's page-size dropdown. */
export const PAGE_SIZES = [25, 50, 100, 250, 500, 1000];

var SampleCollection = Collection.extend({
    resourceName: 'sample',
    model: SampleModel,
    pageLimit: 50,

    _pageLimitKey: function () {
        return `${this.resourceName}.pageLimit`;
    },

    /**
     * Restore the page size the user last picked, the way the deposition list
     * in girder-jsonforms does.
     *
     * Session storage rather than local: a page size chosen to print one
     * batch of labels should last as long as the tab, not forever.
     */
    updateFromSession: function () {
        const stored = parseInt(
            window.sessionStorage.getItem(this._pageLimitKey()), 10);
        // Anything else -- absent, stale, hand-edited -- leaves the default
        // alone, because a NaN page limit fetches nothing at all.
        if (PAGE_SIZES.includes(stored)) {
            this.pageLimit = stored;
        }
        return this;
    },

    setPageLimit: function (limit) {
        this.pageLimit = limit;
        window.sessionStorage.setItem(this._pageLimitKey(), limit);
        return this;
    }
});

export default SampleCollection;
