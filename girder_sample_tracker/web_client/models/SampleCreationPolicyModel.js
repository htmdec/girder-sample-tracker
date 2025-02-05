const { getCurrentUser } = girder.auth;
const { AccessType } = girder.constants;
const AccessControlledModel = girder.models.AccessControlledModel;

var SampleCreationPolicyModel = AccessControlledModel.extend({
    resourceName: 'sampleCreationPolicy',

    fetchAccess: function () {
        var users = [];
        var currentUser = getCurrentUser();
        if (currentUser) {
            users.push({
                'id': currentUser.id,
                'level': AccessType.ADMIN,
                'flags': [],
                'login': currentUser.login,
                'name': currentUser.name()
            });
        }
        this.set('access', {
            groups: [],
            users: users,
            public: false
        });
    }
});

export default SampleCreationPolicyModel;
