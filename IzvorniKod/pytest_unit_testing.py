import pytest
import psycopg2.extensions

from codeshark_backend import connect_to_db
from classes import User, Competition, Task, VirtualCompetition

@pytest.mark.parametrize('expected_type', [psycopg2.extensions.connection])
def test_db_connection(expected_type):
	conn, _ = connect_to_db()
	assert isinstance(conn, expected_type)
	conn.close()

@pytest.mark.parametrize('username, email, expected_result', 
	[('obicansmrtnik1', 'obicansmrtnik@ffzg.hr', True), 
	('incorrect_username', 'incorrect_username@fer.hr', False)])
def test_check_if_user_exists(username, email, expected_result):
	existence = User.check_if_user_exists(username, email)
	assert existence[0] == expected_result

@pytest.mark.parametrize('class_id, expected_result', [(1, 'amater'), (2, 'professional')])
def test_get_class_name(class_id, expected_result):
	name = Competition.get_class_name_from_class_id(class_id)
	# This shouldn't be done when comparing with None (should be "is None") 
	# but to simplify this example
	assert name == expected_result

@pytest.mark.parametrize('slug, expected_result_type', [('area-of-a-sphere', Task), ('wrong-slug', type(None))])
def test_get_task(slug, expected_result_type):
	task, _ = Task.get_task(slug)
	# we can't use isinstance in this case as it can't compare when task is None 
	assert type(task) == expected_result_type

@pytest.mark.parametrize('id, expected_task_name', [(8, 'Area of a sphere')])
def test_get_task_name(id, expected_task_name):
	task_name = Task.get_task_name(id)
	assert task_name == expected_task_name

@pytest.mark.parametrize('virt_id, expected_result_type', [(31, VirtualCompetition)])
def test_get_virtual_competition(virt_id, expected_result_type):
	virt_comp = VirtualCompetition.get_virtual_competition(virt_id)
	assert isinstance(virt_comp[0], expected_result_type)
