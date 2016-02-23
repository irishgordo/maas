# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the commissioning-related portions of the MAAS API."""

__all__ = []

from base64 import b64encode
import http.client

from django.core.urlresolvers import reverse
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import json_load_bytes
from maastesting.utils import sample_binary_data
from metadataserver.models import CommissioningScript


class AdminCommissioningScriptsAPITest(MAASServerTestCase):
    """Tests for `CommissioningScriptsHandler`."""

    def get_url(self):
        return reverse('commissioning_scripts_handler')

    def test_GET_lists_commissioning_scripts(self):
        self.client_log_in(as_admin=True)
        # Use lower-case names.  The database and the test may use
        # different collation orders with different ideas about case
        # sensitivity.
        names = {factory.make_name('script').lower() for counter in range(5)}
        for name in names:
            factory.make_CommissioningScript(name=name)

        response = self.client.get(self.get_url())

        self.assertEqual(
            (http.client.OK, sorted(names)),
            (response.status_code, json_load_bytes(response.content)))

    def test_POST_creates_commissioning_script(self):
        self.client_log_in(as_admin=True)
        # This uses Piston's built-in POST code, so there are no tests for
        # corner cases (like "script already exists") here.
        name = factory.make_name('script')
        content = factory.make_bytes()

        # Every uploaded file also has a name.  But this is completely
        # unrelated to the name we give to the commissioning script.
        response = self.client.post(
            self.get_url(),
            {
                'name': name,
                'content': factory.make_file_upload(content=content),
            })
        self.assertEqual(http.client.OK, response.status_code)

        returned_script = json_load_bytes(response.content)
        self.assertEqual(
            (name, b64encode(content).decode("ascii")),
            (returned_script['name'], returned_script['content']))

        stored_script = CommissioningScript.objects.get(name=name)
        self.assertEqual(content, stored_script.content)


class CommissioningScriptsAPITest(APITestCase):

    def get_url(self):
        return reverse('commissioning_scripts_handler')

    def test_GET_is_forbidden(self):
        response = self.client.get(self.get_url())
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_POST_is_forbidden(self):
        response = self.client.post(
            self.get_url(),
            {'name': factory.make_name('script')})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class AdminCommissioningScriptAPITest(MAASServerTestCase):
    """Tests for `CommissioningScriptHandler`."""

    def get_url(self, script_name):
        return reverse('commissioning_script_handler', args=[script_name])

    def test_GET_returns_script_contents(self):
        self.client_log_in(as_admin=True)
        script = factory.make_CommissioningScript()
        response = self.client.get(self.get_url(script.name))
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(script.content, response.content)

    def test_GET_preserves_binary_data(self):
        self.client_log_in(as_admin=True)
        script = factory.make_CommissioningScript(content=sample_binary_data)
        response = self.client.get(self.get_url(script.name))
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(sample_binary_data, response.content)

    def test_PUT_updates_contents(self):
        self.client_log_in(as_admin=True)
        old_content = b'old:%s' % factory.make_string().encode('ascii')
        script = factory.make_CommissioningScript(content=old_content)
        new_content = b'new:%s' % factory.make_string().encode('ascii')

        response = self.client.put(
            self.get_url(script.name),
            {'content': factory.make_file_upload(content=new_content)})
        self.assertEqual(http.client.OK, response.status_code)

        self.assertEqual(new_content, reload_object(script).content)

    def test_DELETE_deletes_script(self):
        self.client_log_in(as_admin=True)
        script = factory.make_CommissioningScript()
        self.client.delete(self.get_url(script.name))
        self.assertItemsEqual(
            [],
            CommissioningScript.objects.filter(name=script.name))


class CommissioningScriptAPITest(APITestCase):

    def get_url(self, script_name):
        return reverse('commissioning_script_handler', args=[script_name])

    def test_GET_is_forbidden(self):
        # It's not inconceivable that commissioning scripts contain
        # credentials of some sort.  There is no need for regular users
        # (consumers of the MAAS) to see these.
        script = factory.make_CommissioningScript()
        response = self.client.get(self.get_url(script.name))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_is_forbidden(self):
        script = factory.make_CommissioningScript()
        response = self.client.put(
            self.get_url(script.name), {'content': factory.make_string()})
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_is_forbidden(self):
        script = factory.make_CommissioningScript()
        response = self.client.put(self.get_url(script.name))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class NodeCommissionResultHandlerAPITest(APITestCase):

    def test_list_returns_commissioning_results(self):
        commissioning_results = [
            factory.make_NodeResult_for_commissioning()
            for counter in range(3)]
        url = reverse('node_results_handler')
        response = self.client.get(url)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_results = json_load_bytes(response.content)
        self.assertItemsEqual(
            [
                (
                    commissioning_result.name,
                    commissioning_result.script_result,
                    b64encode(commissioning_result.data).decode("utf-8"),
                    commissioning_result.node.system_id,
                )
                for commissioning_result in commissioning_results
            ],
            [
                (
                    result.get('name'),
                    result.get('script_result'),
                    result.get('data'),
                    result.get('node').get('system_id'),
                )
                for result in parsed_results
            ]
        )

    def test_list_can_be_filtered_by_node(self):
        commissioning_results = [
            factory.make_NodeResult_for_commissioning()
            for counter in range(3)]
        url = reverse('node_results_handler')
        response = self.client.get(
            url,
            {
                'system_id': [
                    commissioning_results[0].node.system_id,
                    commissioning_results[1].node.system_id,
                ],
            }
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_results = json_load_bytes(response.content)
        self.assertItemsEqual(
            [b64encode(commissioning_results[0].data).decode("utf-8"),
             b64encode(commissioning_results[1].data).decode("utf-8")],
            [result.get('data') for result in parsed_results])

    def test_list_can_be_filtered_by_name(self):
        commissioning_results = [
            factory.make_NodeResult_for_commissioning()
            for counter in range(3)]
        url = reverse('node_results_handler')
        response = self.client.get(
            url,
            {
                'name': commissioning_results[0].name
            }
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_results = json_load_bytes(response.content)
        self.assertItemsEqual(
            [b64encode(commissioning_results[0].data).decode("utf-8")],
            [result.get('data') for result in parsed_results])

    def test_list_displays_only_visible_nodes(self):
        node = factory.make_Node(owner=factory.make_User())
        factory.make_NodeResult_for_commissioning(node)
        url = reverse('node_results_handler')
        response = self.client.get(url)
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        parsed_results = json_load_bytes(response.content)
        self.assertEqual([], parsed_results)
