# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------
import json
import mock
from azure_devtools.scenario_tests import AllowLargeResponse
from azure.cli.testsdk import ScenarioTest, LiveScenarioTest


class ServicePrincipalExpressCreateScenarioTest(ScenarioTest):

    def test_sp_create_scenario(self):
        app_id_uri = 'http://' + self.create_random_name('clisp-test-', 20)
        self.kwargs['app_id_uri'] = app_id_uri
        # create app through express option
        self.cmd('ad sp create-for-rbac -n {app_id_uri} --skip-assignment',
                 checks=self.check('name', '{app_id_uri}'))

        # show/list app
        self.cmd('ad app show --id {app_id_uri}',
                 checks=self.check('identifierUris[0]', '{app_id_uri}'))
        self.cmd('ad app list --identifier-uri {app_id_uri}', checks=[
            self.check('[0].identifierUris[0]', '{app_id_uri}'),
            self.check('length([*])', 1)
        ])

        # show/list sp
        self.cmd('ad sp show --id {app_id_uri}',
                 checks=self.check('servicePrincipalNames[0]', '{app_id_uri}'))
        self.cmd('ad sp list --spn {app_id_uri}', checks=[
            self.check('[0].servicePrincipalNames[0]', '{app_id_uri}'),
            self.check('length([*])', 1),
        ])
        self.cmd('ad sp credential reset -n {app_id_uri}',
                 checks=self.check('name', '{app_id_uri}'))
        # cleanup
        self.cmd('ad sp delete --id {app_id_uri}')  # this whould auto-delete the app as well
        self.cmd('ad sp list --spn {app_id_uri}',
                 checks=self.is_empty())
        self.cmd('ad app list --identifier-uri {app_id_uri}',
                 checks=self.is_empty())

    def test_native_app_create_scenario(self):
        self.kwargs = {
            'native_app_name': self.create_random_name('cli-native-', 20),
            'required_access': json.dumps([
                {
                    "resourceAppId": "00000002-0000-0000-c000-000000000000",
                    "resourceAccess": [
                        {
                            "id": "5778995a-e1bf-45b8-affa-663a9f3f4d04",
                            "type": "Scope"
                        }
                    ]
                }]),
            'required_access2': json.dumps([
                {
                    "resourceAppId": "00000002-0000-0000-c000-000000000000",
                    "resourceAccess": [
                        {
                            "id": "311a71cc-e848-46a1-bdf8-97ff7156d8e6",
                            "type": "Scope"
                        }
                    ]
                }
            ])
        }
        result = self.cmd("ad app create --display-name {native_app_name} --native-app --required-resource-accesses '{required_access}'", checks=[
            self.check('publicClient', True),
            self.check('requiredResourceAccess|[0].resourceAccess|[0].id',
                       '5778995a-e1bf-45b8-affa-663a9f3f4d04')
        ]).get_output_in_json()
        self.kwargs['id'] = result['appId']
        try:
            self.cmd("ad app update --id {id} --required-resource-accesses '{required_access2}'")
            self.cmd('ad app show --id {id}', checks=[
                self.check('publicClient', True),
                self.check('requiredResourceAccess|[0].resourceAccess|[0].id',
                           '311a71cc-e848-46a1-bdf8-97ff7156d8e6')
            ])
        except Exception:
            self.cmd('ad app delete --id {id}')


class ApplicationSetScenarioTest(ScenarioTest):

    def test_application_set_scenario(self):
        name = self.create_random_name(prefix='cli-graph', length=14)
        self.kwargs.update({
            'app': 'http://' + name,
            'name': name
        })

        # crerate app through general option
        self.cmd('ad app create --display-name {name} --homepage {app} --identifier-uris {app}',
                 checks=self.check('identifierUris[0]', '{app}'))

        # show/list app
        self.cmd('ad app show --id {app}',
                 checks=self.check('identifierUris[0]', '{app}'))
        self.cmd('ad app list --display-name {name}', checks=[
            self.check('[0].identifierUris[0]', '{app}'),
            self.check('length([*])', 1)
        ])

        # update app
        self.kwargs['reply_uri'] = "http://azureclitest-replyuri"
        self.cmd('ad app update --id {app} --reply-urls {reply_uri}')
        self.cmd('ad app show --id {app}',
                 checks=self.check('replyUrls[0]', '{reply_uri}'))

        # invoke generic update
        self.cmd('ad app update --id {app} --set oauth2AllowUrlPathMatching=true')
        self.cmd('ad app show --id {app}',
                 checks=self.check('oauth2AllowUrlPathMatching', True))

        # delete app
        self.cmd('ad app delete --id {app}')
        self.cmd('ad app list --identifier-uri {app}',
                 checks=self.is_empty())


class CreateForRbacScenarioTest(ScenarioTest):

    @AllowLargeResponse()
    def test_revoke_sp_for_rbac(self):
        name = self.create_random_name(prefix='cli-graph', length=14)
        self.kwargs['name'] = 'http://' + name

        with mock.patch('azure.cli.command_modules.role.custom._gen_guid', side_effect=self.create_guid):
            self.cmd('ad sp create-for-rbac -n {name}')

            self.cmd('ad sp list --spn {name}')

            self.cmd('ad app list --identifier-uri {name}')

            result = self.cmd('role assignment list --assignee {name}').get_output_in_json()
            object_id = result[0]['principalId']

            self.cmd('ad sp delete --id {name}')

            result2 = self.cmd('role assignment list --all').get_output_in_json()
            self.assertFalse([a for a in result2 if a['id'] == object_id])

            self.cmd('ad sp list --spn {name}',
                     checks=self.check('length([])', 0))
            self.cmd('ad app list --identifier-uri {name}',
                     checks=self.check('length([])', 0))


class GraphGroupScenarioTest(ScenarioTest):

    def test_graph_group_scenario(self):

        account_info = self.cmd('account show').get_output_in_json()
        if account_info['user']['type'] == 'servicePrincipal':
            return  # this test delete users which are beyond a SP's capacity, so quit...
        upn = account_info['user']['name']

        self.kwargs = {
            'user1': 'deleteme1',
            'user2': 'deleteme2',
            'domain': upn.split('@', 1)[1],
            'group': 'deleteme_g',
            'pass': 'Test1234!!'
        }
        try:
            # create user1
            user1_result = self.cmd('ad user create --display-name {user1} --password {pass} --user-principal-name {user1}@{domain}').get_output_in_json()
            self.kwargs['user1_id'] = user1_result['objectId']
            # create user2
            user2_result = self.cmd('ad user create --display-name {user2} --password {pass} --user-principal-name {user2}@{domain}').get_output_in_json()
            self.kwargs['user2_id'] = user2_result['objectId']
            # create group
            group_result = self.cmd('ad group create --display-name {group} --mail-nickname {group}').get_output_in_json()
            self.kwargs['group_id'] = group_result['objectId']
            # add user1 into group
            self.cmd('ad group member add -g {group} --member-id {user1_id}',
                     checks=self.is_empty())
            # add user2 into group
            self.cmd('ad group member add -g {group} --member-id {user2_id}',
                     checks=self.is_empty())
            # show group
            self.cmd('ad group show -g {group}', checks=[
                self.check('objectId', '{group_id}'),
                self.check('displayName', '{group}')
            ])
            self.cmd('ad group show -g {group}',
                     checks=self.check('displayName', '{group}'))
            # list group
            self.cmd('ad group list --display-name {group}',
                     checks=self.check('[0].displayName', '{group}'))
            # show member groups
            self.cmd('ad group get-member-groups -g {group}',
                     checks=self.check('length([])', 0))
            # check user1 memebership
            self.cmd('ad group member check -g {group} --member-id {user1_id}',
                     checks=self.check('value', True))
            # check user2 memebership
            self.cmd('ad group member check -g {group} --member-id {user2_id}',
                     checks=self.check('value', True))            # list memebers
            self.cmd('ad group member list -g {group}', checks=[
                self.check("length([?displayName=='{user1}'])", 1),
                self.check("length([?displayName=='{user2}'])", 1),
                self.check("length([])", 2),
            ])
            # remove user1
            self.cmd('ad group member remove -g {group} --member-id {user1_id}')
            # check user1 memebership
            self.cmd('ad group member check -g {group} --member-id {user1_id}',
                     checks=self.check('value', False))
            # delete the group
            self.cmd('ad group delete -g {group}')
            self.cmd('ad group list',
                     checks=self.check("length([?displayName=='{group}'])", 0))
        finally:
            try:
                self.cmd('ad user delete --upn-or-object-id {user1_id}')
                self.cmd('ad user delete --upn-or-object-id {user2_id}')
                self.cmd('ad group delete -g {group}')
            except Exception:
                pass
