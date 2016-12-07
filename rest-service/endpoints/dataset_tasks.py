#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# coding:utf-8
#
# dataset_tasks.py: Falcon file to manage resources which creates tasks
# Copyright (C) 2016  Víctor Fernández Rico <vfrico@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import copy
import falcon
import kgeserver.server as server
import endpoints.common_hooks as common_hooks

# Import parent directory (data_access)
import sys
sys.path.insert(0, '..')
try:
    import data_access
    import async_server.tasks as async_tasks
except ImportError:
    raise


def read_body_generate_triples(req, resp, resource, params):
    try:
        body = common_hooks.read_body_as_json(req)

        json_rpc = body['generate_triples']
        if "levels" not in json_rpc:
            msg = ("The 'generate_triples' JSON object must contain"
                   "level attribute")
            raise falcon.HTTPInvalidParam(msg, "levels")
    except KeyError as err:
        raise falcon.HTTPMissingParam(err(str))


class GenerateTriplesResource():
    @falcon.before(read_body_generate_triples)
    @falcon.before(common_hooks.dataset_untrained_status)
    @falcon.before(common_hooks.check_dataset_exsistence)
    def on_post(self, req, resp, dataset_id, dataset_dto, json_rpc):
        """Generates a task to insert triples on dataset. Async petition.

        Reads from body the parameters such as SPARQL queries

        {"generate_triples":
            {
                "graph_pattern": "<SPARQL Query (Where part)>",
                "levels": 2,
                "batch_size": 30000   # Optional
            }
        }

        :param id dataset_id: The dataset to insert triples into
        :param DTO dataset_dto: The Dataset DTO from dataset_id (from hook)
        :param dict json_rpc: Params to call generate_triples func (from hook)
        """
        # Read arguments from body
        graph_pattern = json_rpc.pop("graph_pattern")
        levels = json_rpc.pop("levels")
        try:
            batch_size = json_rpc.pop("batch_size")
        except KeyError:
            batch_size = None

        # Launch async task
        task = async_tasks.generate_dataset_from_sparql.delay(
            dataset_id, graph_pattern, levels, batch_size=batch_size)

        # Create a new task
        task_dao = data_access.TaskDAO()
        task_obj, err = task_dao.add_task_by_uuid(task.id)
        if task_obj is None:
            raise falcon.HTTPNotFound(description=str(err))
        task_obj["next"] = "/datasets/" + dataset_id
        task_dao.update_task(task_obj)

        msg = "Task {} created successfuly".format(task_obj['id'])
        textbody = {"status": 202, "message": msg}
        resp.location = "/tasks/" + str(task_obj['id'])
        resp.body = json.dumps(textbody)
        resp.content_type = 'application/json'
        resp.status = falcon.HTTP_202


class DatasetIndex():
    # TODO: Save anywhere the number of trees used
    @falcon.before(common_hooks.dataset_trained_status)
    @falcon.before(common_hooks.check_dataset_exsistence)
    def on_post(self, req, resp, dataset_id, dataset_dto):
        """Generates a search index to perform data lookups operations.

        This task may take long time to complete, so it uses tasks.

        :query int n_trees: The number of trees generated
        :param id dataset_id: The dataset to insert triples into
        :param DTO dataset_dto: The Dataset DTO from dataset_id (from hook)
        """

        # Dig for the param on Query Params
        n_trees = req.get_param_as_int('n_trees')

        # Call to the task
        task = async_tasks.build_search_index.delay(dataset_id, n_trees)

        # Create the new task
        task_dao = data_access.TaskDAO()
        task_obj, err = task_dao.add_task_by_uuid(task.id)
        if task_obj is None:
            raise falcon.HTTPNotFound(description=str(err))
        task_obj["next"] = "/datasets/" + dataset_id
        task_dao.update_task(task_obj)

        msg = "Task {} created successfuly".format(task_obj['id'])
        textbody = {"status": 202, "message": msg}
        resp.location = "/tasks/" + str(task_obj['id'])
        resp.body = json.dumps(textbody)
        resp.content_type = 'application/json'
        resp.status = falcon.HTTP_202


class DatasetTrain():
    # TODO: Test if works well
    @falcon.before(common_hooks.dataset_untrained_status)
    @falcon.before(common_hooks.check_dataset_exsistence)
    def on_post(self, req, resp, dataset_id, dataset_dto):
        """Generates a model that fits the dataset and trains it

        It usually takes several hours for big datasets

        This changes the dataset status from 0 to 1 once finished. While
        training takes place, the status will be set to a negative value.

        :param id dataset_id: The dataset to insert triples into
        :param DTO dataset_dto: The Dataset DTO from dataset_id (from hook)
        :query int algorithm_id: The algorithm used to train the dataset
        """
        # Dig for the limit param on Query Params
        algorithm_id = req.get_param('algorithm_id', required=True)

        # Obtain the algorithm
        algorithm_dao = data_access.AlgorithmDAO()
        algorithm, err = algorithm_dao.get_algorithm_by_id(algorithm_id)
        if algorithm is None:
            raise falcon.HTTPNotFound(message=str(err))

        # Launch async task
        task = async_tasks.train_dataset_from_algorithm.delay(
            dataset_id, algorithm)

        # Create the new task
        task_dao = data_access.TaskDAO()
        task_obj, err = task_dao.add_task_by_uuid(task.id)
        if task_obj is None:
            raise falcon.HTTPNotFound(description=str(err))
        task_obj["next"] = "/datasets/" + dataset_id
        task_dao.update_task(task_obj)

        msg = "Task {} created successfuly".format(task_obj['id'])
        textbody = {"status": 202, "message": msg}
        resp.location = "/tasks/" + str(task_obj['id'])
        resp.body = json.dumps(textbody)
        resp.content_type = 'application/json'
        resp.status = falcon.HTTP_202
