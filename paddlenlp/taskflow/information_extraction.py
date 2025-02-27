# coding:utf-8
# Copyright (c) 2022  PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import numpy as np
import paddle
from ..datasets import load_dataset
from ..transformers import AutoTokenizer
from .models import UIE
from .task import Task
from .utils import SchemaTree, get_span, get_id_and_prob, get_bool_ids_greater_than, dbc2sbc

usage = r"""
            from paddlenlp import Taskflow

            # Entity Extraction
            schema = ['时间', '选手', '赛事名称'] # Define the schema for entity extraction
            ie = Taskflow('information_extraction', schema=schema)
            ie("2月8日上午北京冬奥会自由式滑雪女子大跳台决赛中中国选手谷爱凌以188.25分获得金牌！")
            '''
            [{'时间': [{'text': '2月8日上午', 'start': 0, 'end': 6, 'probability': 0.9907337794563702}], '选手': [{'text': '谷爱凌', 'start': 28, 'end': 31, 'probability': 0.8914310308098763}], '赛事名称': [{'text': '北京冬奥会自由式滑雪女子大跳台决赛', 'start': 6, 'end': 23, 'probability': 0.8944207860063003}]}]
            '''

            # Relation Extraction
            schema = [{"歌曲名称":["歌手", "所属专辑"]}] # Define the schema for relation extraction
            ie.set_schema(schema) # Reset schema
            ie("《告别了》是孙耀威在专辑爱的故事里面的歌曲")
            '''
            [{'歌曲名称': [{'text': '告别了', 'start': 1, 'end': 4, 'probability': 0.7721050787207417, 'relations': {'歌手': [{'text': '孙耀威', 'start': 6, 'end': 9, 'probability': 0.9996328066160487}], '所属专辑': [{'text': '爱的故事', 'start': 12, 'end': 16, 'probability': 0.9981007942846247}]}}]}]
            '''

            # Event Extraction
            schema = [{'地震触发词': ['地震强度', '时间', '震中位置', '震源深度']}] # Define the schema for event extraction
            ie.set_schema(schema) # Reset schema
            ie('中国地震台网正式测定：5月16日06时08分在云南临沧市凤庆县(北纬24.34度，东经99.98度)发生3.5级地震，震源深度10千米。')
            '''
            [{'地震触发词': [{'text': '地震', 'start': 56, 'end': 58, 'probability': 0.9987181623528585, 'relation': {'地震强度': [{'text': '3.5级', 'start': 52, 'end': 56, 'probability': 0.9962985320905915}], '时间': [{'text': '5月16日06时08分', 'start': 11, 'end': 22, 'probability': 0.9882578028575182}], '震中位置': [{'text': '云南临沧市凤庆县(北纬24.34度，东经99.98度)', 'start': 23, 'end': 50, 'probability': 0.8551415716584501}], '震源深度': [{'text': '10千米', 'start': 63, 'end': 67, 'probability': 0.999158304648045}]}}]}]
            '''

            # Opinion Extraction
            schema = [{'评价维度': ['观点词']}] # Define the schema for opinion extraction
            ie.set_schema(schema) # Reset schema
            ie('个人觉得管理太混乱了，票价太高了')
            '''
            [{'评价维度': [{'text': '管理', 'start': 4, 'end': 6, 'probability': 0.8902373594544031, 'relation': {'观点词': [{'text': '混乱', 'start': 7, 'end': 9, 'probability': 0.9993566520321409}]}}, {'text': '票价', 'start': 11, 'end': 13, 'probability': 0.9856116411308662, 'relation': {'观点词': [{'text': '高', 'start': 14, 'end': 15, 'probability': 0.995628420935013}]}}]}]
            '''

            # Sentence-level Sentiment Classification
            schema = ['情感倾向[正向，负向]'] # Define the schema for sentence-level sentiment classification
            ie.set_schema(schema) # Reset schema
            ie('这个产品用起来真的很流畅，我非常喜欢')
            '''
            [{'情感倾向[正向，负向]': [{'text': '正向', 'probability': 0.9990110458312529}]}]
            '''
         """


class UIETask(Task):
    """
    Universal Information Extraction Task. 
    Args:
        task(string): The name of task.
        model(string): The model name in the task.
        kwargs (dict, optional): Additional keyword arguments passed along to the specific task. 
    """

    resource_files_names = {"model_state": "model_state.pdparams", }
    resource_files_urls = {
        "uie-base": {
            "model_state": [
                "https://bj.bcebos.com/paddlenlp/taskflow/information_extraction/uie_base/model_state.pdparams",
                "004d7e53f5222349741217fabfb241ac"
            ],
        },
        "uie-tiny": {
            "model_state": [
                "https://bj.bcebos.com/paddlenlp/taskflow/information_extraction/uie_tiny/model_state.pdparams",
                "6248b4897fec78a61ab6da3edf9707fe"
            ],
        },
        "uie-medical-base": {
            "model_state": [
                "https://bj.bcebos.com/paddlenlp/taskflow/information_extraction/uie_medical_base/model_state.pdparams",
                "56c2b7d02403f2ede513cedaabc8212a"
            ],
        },
    }

    def __init__(self, task, model, schema, **kwargs):
        super().__init__(task=task, model=model, **kwargs)
        self.set_schema(schema)
        if model in ["uie-base", "uie-medical-base"]:
            self._encoding_model = "ernie-3.0-base-zh"
        elif model == "uie-tiny":
            self._encoding_model = "ernie-3.0-medium-zh"
        else:
            raise ValueError(
                "Model should be one of uie-base, uie-tiny and uie-medical-base")
        self._check_task_files()
        self._construct_tokenizer()
        self._get_inference_model()
        self._usage = usage
        self._max_seq_len = self.kwargs[
            'max_seq_len'] if 'max_seq_len' in self.kwargs else 512
        self._batch_size = self.kwargs[
            'batch_size'] if 'batch_size' in self.kwargs else 64
        self._split_sentence = self.kwargs[
            'split_sentence'] if 'split_sentence' in self.kwargs else False
        self._position_prob = self.kwargs[
            'position_prob'] if 'position_prob' in self.kwargs else 0.5

    def set_schema(self, schema):
        if isinstance(schema, dict) or isinstance(schema, str):
            schema = [schema]
        self._schema = schema
        self._build_tree(self._schema)

    def _construct_input_spec(self):
        """
        Construct the input spec for the convert dygraph model to static model.
        """
        self._input_spec = [
            paddle.static.InputSpec(
                shape=[None, None], dtype="int64", name='input_ids'),
            paddle.static.InputSpec(
                shape=[None, None], dtype="int64", name='token_type_ids'),
            paddle.static.InputSpec(
                shape=[None, None], dtype="int64", name='pos_ids'),
            paddle.static.InputSpec(
                shape=[None, None], dtype="int64", name='att_mask'),
        ]

    def _construct_model(self, model):
        """
        Construct the inference model for the predictor.
        """
        model_instance = UIE(self._encoding_model, self.kwargs['hidden_size'])
        model_path = os.path.join(self._task_path, "model_state.pdparams")

        # Load the model parameter for the predict
        state_dict = paddle.load(model_path)
        model_instance.set_dict(state_dict)
        self._model = model_instance
        self._model.eval()

    def _construct_tokenizer(self):
        """
        Construct the tokenizer for the predictor.
        """
        self._tokenizer = AutoTokenizer.from_pretrained(self._encoding_model)

    def _preprocess(self, inputs):
        """
        Transform the raw text to the model inputs, two steps involved:
           1) Transform the raw text to token ids.
           2) Generate the other model inputs from the raw text and token ids.
        """
        inputs = self._check_input_text(inputs)
        outputs = {}
        outputs['text'] = inputs
        return outputs

    def _single_stage_predict(self, inputs):
        input_texts = []
        prompts = []
        for i in range(len(inputs)):
            input_texts.append(inputs[i]["text"])
            prompts.append(inputs[i]["prompt"])
        # max predict length should exclude the length of prompt and summary tokens
        max_predict_len = self._max_seq_len - len(max(prompts)) - 3

        short_input_texts, self.input_mapping = self._auto_splitter(
            input_texts, max_predict_len, split_sentence=self._split_sentence)

        short_texts_prompts = []
        for k, v in self.input_mapping.items():
            short_texts_prompts.extend([prompts[k] for i in range(len(v))])
        short_inputs = [{
            "text": short_input_texts[i],
            "prompt": short_texts_prompts[i]
        } for i in range(len(short_input_texts))]

        def read(inputs):
            for example in inputs:
                encoded_inputs = self._tokenizer(
                    text=[example["prompt"]],
                    text_pair=[example["text"]],
                    stride=len(example["prompt"]),
                    truncation=True,
                    max_seq_len=self._max_seq_len,
                    pad_to_max_seq_len=True,
                    return_attention_mask=True,
                    return_position_ids=True,
                    return_dict=False)
                encoded_inputs = encoded_inputs[0]

                tokenized_output = [
                    encoded_inputs["input_ids"],
                    encoded_inputs["token_type_ids"],
                    encoded_inputs["position_ids"],
                    encoded_inputs["attention_mask"],
                    encoded_inputs["offset_mapping"]
                ]
                tokenized_output = [
                    np.array(
                        x, dtype="int64") for x in tokenized_output
                ]

                yield tuple(tokenized_output)

        infer_ds = load_dataset(read, inputs=short_inputs, lazy=False)
        batch_sampler = paddle.io.BatchSampler(
            dataset=infer_ds, batch_size=self._batch_size, shuffle=False)

        infer_data_loader = paddle.io.DataLoader(
            dataset=infer_ds, batch_sampler=batch_sampler, return_list=True)

        sentence_ids = []
        probs = []
        for batch in infer_data_loader:
            input_ids, token_type_ids, pos_ids, att_mask, offset_maps = batch
            self.input_handles[0].copy_from_cpu(input_ids.numpy())
            self.input_handles[1].copy_from_cpu(token_type_ids.numpy())
            self.input_handles[2].copy_from_cpu(pos_ids.numpy())
            self.input_handles[3].copy_from_cpu(att_mask.numpy())
            self.predictor.run()
            start_prob = self.output_handle[0].copy_to_cpu().tolist()
            end_prob = self.output_handle[1].copy_to_cpu().tolist()

            start_ids_list = get_bool_ids_greater_than(
                start_prob, limit=self._position_prob, return_prob=True)
            end_ids_list = get_bool_ids_greater_than(
                end_prob, limit=self._position_prob, return_prob=True)

            for start_ids, end_ids, ids, offset_map in zip(
                    start_ids_list, end_ids_list,
                    input_ids.tolist(), offset_maps.tolist()):
                for i in reversed(range(len(ids))):
                    if ids[i] != 0:
                        ids = ids[:i]
                        break
                span_list = get_span(start_ids, end_ids, with_prob=True)
                sentence_id, prob = get_id_and_prob(span_list, offset_map)
                sentence_ids.append(sentence_id)
                probs.append(prob)
        results = self._convert_ids_to_results(short_inputs, sentence_ids,
                                               probs)
        results = self._auto_joiner(results, short_input_texts,
                                    self.input_mapping)
        return results

    def _auto_joiner(self, short_results, short_inputs, input_mapping):
        concat_results = []
        is_cls_task = False
        for short_result in short_results:
            if short_result == []:
                continue
            elif 'start' not in short_result[0].keys(
            ) and 'end' not in short_result[0].keys():
                is_cls_task = True
                break
            else:
                break
        for k, vs in input_mapping.items():
            if is_cls_task:
                cls_options = {}
                single_results = []
                for v in vs:
                    if len(short_results[v]) == 0:
                        continue
                    if short_results[v][0]['text'] not in cls_options.keys():
                        cls_options[short_results[v][0][
                            'text']] = [1, short_results[v][0]['probability']]
                    else:
                        cls_options[short_results[v][0]['text']][0] += 1
                        cls_options[short_results[v][0]['text']][
                            1] += short_results[v][0]['probability']
                if len(cls_options) != 0:
                    cls_res, cls_info = max(cls_options.items(),
                                            key=lambda x: x[1])
                    concat_results.append([{
                        'text': cls_res,
                        'probability': cls_info[1] / cls_info[0]
                    }])
                else:
                    concat_results.append([])
            else:
                offset = 0
                single_results = []
                for v in vs:
                    if v == 0:
                        single_results = short_results[v]
                        offset += len(short_inputs[v])
                    else:
                        for i in range(len(short_results[v])):
                            if 'start' not in short_results[v][
                                    i] or 'end' not in short_results[v][i]:
                                continue
                            short_results[v][i]['start'] += offset
                            short_results[v][i]['end'] += offset
                        offset += len(short_inputs[v])
                        single_results.extend(short_results[v])
                concat_results.append(single_results)
        return concat_results

    def _run_model(self, inputs):
        raw_inputs = inputs['text']
        schema_tree = self._build_tree(self._schema)
        results = self._multi_stage_predict(raw_inputs, schema_tree)
        inputs['result'] = results
        return inputs

    def _multi_stage_predict(self, datas, schema_tree):
        """
        Traversal the schema tree and do multi-stage prediction.
        """
        results = [{} for i in range(len(datas))]
        schema_list = schema_tree.children
        while len(schema_list) > 0:
            node = schema_list.pop(0)
            examples = []
            input_map = {}
            cnt = 0
            id = 0
            if not node.prefix:
                for data in datas:
                    examples.append({
                        "text": data,
                        "prompt": dbc2sbc(node.name)
                    })
                    input_map[cnt] = [id]
                    id += 1
                    cnt += 1
            else:
                for pre, data in zip(node.prefix, datas):
                    if len(pre) == 0:
                        input_map[cnt] = []
                    else:
                        for p in pre:
                            examples.append({
                                "text": data,
                                "prompt": dbc2sbc(p + node.name)
                            })
                        input_map[cnt] = [i + id for i in range(len(pre))]
                        id += len(pre)
                    cnt += 1
            if len(examples) == 0:
                result_list = []
            else:
                result_list = self._single_stage_predict(examples)

            if not node.parent_relations:
                relations = [[] for i in range(len(datas))]
                for k, v in input_map.items():
                    for id in v:
                        if len(result_list[id]) == 0:
                            continue
                        if node.name not in results[k].keys():
                            results[k][node.name] = result_list[id]
                        else:
                            results[k][node.name].extend(result_list[id])
                    if node.name in results[k].keys():
                        relations[k].extend(results[k][node.name])
            else:
                relations = node.parent_relations
                for k, v in input_map.items():
                    for i in range(len(v)):
                        if len(result_list[v[i]]) == 0:
                            continue
                        if "relations" not in relations[k][i].keys():
                            relations[k][i]["relations"] = {
                                node.name: result_list[v[i]]
                            }
                        elif node.name not in relations[k][i]["relations"].keys(
                        ):
                            relations[k][i]["relations"][
                                node.name] = result_list[v[i]]
                        else:
                            relations[k][i]["relations"][node.name].extend(
                                result_list[v[i]])
                new_relations = [[] for i in range(len(datas))]
                for i in range(len(relations)):
                    for j in range(len(relations[i])):
                        if "relations" in relations[i][j].keys(
                        ) and node.name in relations[i][j]["relations"].keys():
                            for k in range(
                                    len(relations[i][j]["relations"][
                                        node.name])):
                                new_relations[i].append(relations[i][j][
                                    "relations"][node.name][k])
                relations = new_relations

            prefix = [[] for i in range(len(datas))]
            for k, v in input_map.items():
                for id in v:
                    for i in range(len(result_list[id])):
                        prefix[k].append(result_list[id][i]["text"] + "的")

            for child in node.children:
                child.prefix = prefix
                child.parent_relations = relations
                schema_list.append(child)
        return results

    def _convert_ids_to_results(self, examples, sentence_ids, probs):
        """
        Convert ids to raw text in a single stage.
        """
        results = []
        for example, sentence_id, prob in zip(examples, sentence_ids, probs):
            if len(sentence_id) == 0:
                results.append([])
                continue
            result_list = []
            text = example["text"]
            prompt = example["prompt"]
            for i in range(len(sentence_id)):
                start, end = sentence_id[i]
                if start < 0 and end >= 0:
                    continue
                if end < 0:
                    start += (len(prompt) + 1)
                    end += (len(prompt) + 1)
                    result = {"text": prompt[start:end], "probability": prob[i]}
                    result_list.append(result)
                else:
                    result = {
                        "text": text[start:end],
                        "start": start,
                        "end": end,
                        "probability": prob[i]
                    }
                    result_list.append(result)
            results.append(result_list)
        return results

    def _build_tree(self, schema, name='root'):
        """
        Build the schema tree.
        """
        schema_tree = SchemaTree(name)
        for s in schema:
            if isinstance(s, str):
                schema_tree.add_child(SchemaTree(s))
            elif isinstance(s, dict):
                for k, v in s.items():
                    if isinstance(v, str):
                        child = [v]
                    elif isinstance(v, list):
                        child = v
                    else:
                        raise TypeError(
                            "Invalid schema, value for each key:value pairs should be list or string"
                            "but {} received".format(type(v)))
                    schema_tree.add_child(self._build_tree(child, name=k))
            else:
                raise TypeError(
                    "Invalid schema, element should be string or dict, "
                    "but {} received".format(type(s)))
        return schema_tree

    def _postprocess(self, inputs):
        """
        This function will convert the model output to raw text.
        """
        return inputs['result']
