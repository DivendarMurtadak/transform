# Lint as: python3
# coding=utf-8
#
# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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
"""Tests for tft.vocabulary and tft.compute_and_apply_vocabulary."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

# GOOGLE-INITIALIZATION

import apache_beam as beam
from apache_beam.testing import util as beam_test_util
import six

import tensorflow as tf
import tensorflow_transform as tft
from tensorflow_transform.beam import impl as beam_impl
from tensorflow_transform.beam import tft_unit
from tensorflow_transform.beam.tft_beam_io import transform_fn_io
from tensorflow_metadata.proto.v0 import schema_pb2


class VocabularyIntegrationTest(tft_unit.TransformTestCase):

  # From testVocabularyAnalyzerStringVsIntegerFeature
  _WITH_LABEL_PARAMS = tft_unit.cross_named_parameters([
      dict(
          testcase_name='string',
          x_data=[
              b'hello', b'hello', b'hello', b'goodbye', b'aaaaa', b'aaaaa',
              b'goodbye', b'goodbye', b'aaaaa', b'aaaaa', b'goodbye', b'goodbye'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          expected_vocab_file_contents=[(b'goodbye', 1.975322),
                                        (b'aaaaa', 1.6600708),
                                        (b'hello', 1.2450531)]),
      dict(
          testcase_name='int64',
          x_data=[3, 3, 3, 1, 2, 2, 1, 1, 2, 2, 1, 1],
          x_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          expected_vocab_file_contents=[(b'1', 1.975322), (b'2', 1.6600708),
                                        (b'3', 1.2450531)]),
  ], [
      dict(
          testcase_name='with_label',
          label_data=[1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          min_diff_from_avg=0.0,
          store_frequency=True),
  ])

  @tft_unit.named_parameters(*([
      # NOTE: Since these tests are a refactoring of existing tests, each test
      # case parameter (or parameters where the original test was parameterized
      # or tested multiple calls to tft.vocabulary) has a comment indicating the
      # test case that it is based on.  This preserves the ability to track the
      # proveance of the test case parameters in the git history.
      # TODO(KesterTong): Remove these annotations and the above comment.
      # From testVocabularyWithMutualInformation
      dict(
          testcase_name='unadjusted_mi_binary_label',
          x_data=[
              b'informative', b'informative', b'informative', b'uninformative',
              b'uninformative', b'uninformative', b'uninformative',
              b'uninformative_rare', b'uninformative_rare'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[1, 1, 1, 0, 1, 1, 0, 0, 1],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          expected_vocab_file_contents=[
              (b'informative', 1.7548264),
              (b'uninformative', 0.33985),
              (b'uninformative_rare', 0.169925),
          ],
          min_diff_from_avg=0.0,
          use_adjusted_mutual_info=False,
          store_frequency=True),
      dict(
          testcase_name='unadjusted_mi_multi_class_label',
          x_data=[
              b'good_predictor_of_0', b'good_predictor_of_0',
              b'good_predictor_of_0', b'good_predictor_of_1',
              b'good_predictor_of_2', b'good_predictor_of_2',
              b'good_predictor_of_2', b'good_predictor_of_1',
              b'good_predictor_of_1', b'weak_predictor_of_1',
              b'good_predictor_of_0', b'good_predictor_of_1',
              b'good_predictor_of_1', b'good_predictor_of_1',
              b'weak_predictor_of_1'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[0, 0, 0, 1, 2, 2, 2, 1, 1, 1, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          expected_vocab_file_contents=[
              (b'good_predictor_of_2', 6.9656615),
              (b'good_predictor_of_1', 6.5969831),
              (b'good_predictor_of_0', 6.3396921),
              (b'weak_predictor_of_1', 0.684463),
          ],
          min_diff_from_avg=0.0,
          use_adjusted_mutual_info=False,
          store_frequency=True),
      dict(
          testcase_name='unadjusted_mi_binary_label_with_weights',
          x_data=[
              b'informative_1', b'informative_1', b'informative_0',
              b'informative_0', b'uninformative', b'uninformative',
              b'informative_by_weight', b'informative_by_weight'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[1, 1, 0, 0, 0, 1, 0, 1],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          # uninformative and informative_by_weight have the same co-occurrence
          # relationship with the label but will have different importance
          # values due to the weighting.
          expected_vocab_file_contents=[
              (b'informative_0', 3.1698803),
              (b'informative_1', 1.1698843),
              (b'informative_by_weight', 0.6096405),
              (b'uninformative', 0.169925),
          ],
          weight_data=[1, 1, 1, 1, 1, 1, 1, 5],
          weight_feature_spec=tf.io.FixedLenFeature([], tf.float32),
          min_diff_from_avg=0.0,
          use_adjusted_mutual_info=False,
          store_frequency=True),
      dict(
          testcase_name='unadjusted_mi_binary_label_min_diff_from_avg',
          x_data=[
              b'hello', b'hello', b'hello', b'goodbye', b'aaaaa', b'aaaaa',
              b'goodbye', b'goodbye', b'aaaaa', b'aaaaa', b'goodbye', b'goodbye'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          # All features are weak predictors, so all are adjusted to zero.
          expected_vocab_file_contents=[
              (b'hello', 0.0),
              (b'goodbye', 0.0),
              (b'aaaaa', 0.0),
          ],
          use_adjusted_mutual_info=False,
          min_diff_from_avg=2.0,
          store_frequency=True),
      dict(
          testcase_name='adjusted_mi_binary_label',
          x_data=[
              b'hello', b'hello', b'hello', b'goodbye', b'aaaaa', b'aaaaa',
              b'goodbye', b'goodbye', b'aaaaa', b'aaaaa', b'goodbye', b'goodbye'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          expected_vocab_file_contents=[
              (b'goodbye', 1.4070791),
              (b'aaaaa', 0.9987449),
              (b'hello', 0.5017179),
          ],
          min_diff_from_avg=0.0,
          use_adjusted_mutual_info=True,
          store_frequency=True),
      dict(
          testcase_name='adjusted_mi_binary_label_int64_feature',
          x_data=[3, 3, 3, 1, 2, 2, 1, 1, 2, 2, 1, 1],
          x_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          label_data=[1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          expected_vocab_file_contents=[
              (b'1', 1.4070791),
              (b'2', 0.9987449),
              (b'3', 0.5017179),
          ],
          min_diff_from_avg=0.0,
          use_adjusted_mutual_info=True,
          store_frequency=True),
      dict(
          testcase_name='adjusted_mi_multi_class_label',
          x_data=[
              b'good_predictor_of_0', b'good_predictor_of_0',
              b'good_predictor_of_0', b'good_predictor_of_1',
              b'good_predictor_of_2', b'good_predictor_of_2',
              b'good_predictor_of_2', b'good_predictor_of_1',
              b'good_predictor_of_1', b'weak_predictor_of_1',
              b'good_predictor_of_0', b'good_predictor_of_1',
              b'good_predictor_of_1', b'good_predictor_of_1',
              b'weak_predictor_of_1'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[0, 0, 0, 1, 2, 2, 2, 1, 1, 1, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          expected_vocab_file_contents=[
              (b'good_predictor_of_1', 5.4800903),
              (b'good_predictor_of_2', 5.386102),
              (b'good_predictor_of_0', 4.9054723),
              (b'weak_predictor_of_1', -0.9748023),
          ],
          min_diff_from_avg=0.0,
          use_adjusted_mutual_info=True,
          store_frequency=True),
      # TODO(b/128831096): Determine correct interaction between AMI and weights
      dict(
          testcase_name='adjusted_mi_binary_label_with_weights',
          x_data=[
              b'informative_1', b'informative_1', b'informative_0',
              b'informative_0', b'uninformative', b'uninformative',
              b'informative_by_weight', b'informative_by_weight'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[1, 1, 0, 0, 0, 1, 0, 1],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          weight_data=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 5.0],
          weight_feature_spec=tf.io.FixedLenFeature([], tf.float32),
          # uninformative and informative_by_weight have the same co-occurrence
          # relationship with the label but will have different importance
          # values due to the weighting.
          expected_vocab_file_contents=[
              (b'informative_0', 2.3029856),
              (b'informative_1', 0.3029896),
              (b'informative_by_weight', 0.1713041),
              (b'uninformative', -0.6969697),
          ],
          min_diff_from_avg=0.0,
          use_adjusted_mutual_info=True,
          store_frequency=True),
      dict(
          testcase_name='adjusted_mi_min_diff_from_avg',
          x_data=[
              b'good_predictor_of_0', b'good_predictor_of_0',
              b'good_predictor_of_0', b'good_predictor_of_1',
              b'good_predictor_of_0', b'good_predictor_of_1',
              b'good_predictor_of_1', b'good_predictor_of_1',
              b'good_predictor_of_1', b'good_predictor_of_0',
              b'good_predictor_of_1', b'good_predictor_of_1',
              b'good_predictor_of_1', b'weak_predictor_of_1',
              b'weak_predictor_of_1'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[0, 0, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          # With min_diff_from_avg, the small AMI value is regularized to 0
          expected_vocab_file_contents=[
              (b'good_predictor_of_0', 1.8322128),
              (b'good_predictor_of_1', 1.7554416),
              (b'weak_predictor_of_1', 0),
          ],
          use_adjusted_mutual_info=True,
          min_diff_from_avg=1.0,
          store_frequency=True),
      # From testVocabularyAnalyzerWithLabelsWeightsAndFrequency
      dict(
          testcase_name='labels_weight_and_frequency',
          x_data=[
              b'hello', b'hello', b'hello', b'goodbye', b'aaaaa', b'aaaaa',
              b'goodbye', b'goodbye', b'aaaaa', b'aaaaa', b'goodbye', b'goodbye'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          weight_data=[
              0.3, 0.4, 0.3, 1.2, 0.6, 0.7, 1.0, 1.0, 0.6, 0.7, 1.0, 1.0
          ],
          weight_feature_spec=tf.io.FixedLenFeature([], tf.float32),
          expected_vocab_file_contents=[
              (b'aaaaa', 1.5637185),
              (b'goodbye', 0.8699492),
              (b'hello', 0.6014302),
          ],
          min_diff_from_avg=0.0,
          store_frequency=True),
      # From testVocabularyWithFrequencyAndFingerprintShuffle
      # fingerprints by which each of the tokens will be sorted if fingerprint
      # shuffling is used.
      # 'ho ho': '1b3dd735ddff70d90f3b7ba5ebf65df521d6ca4d'
      # 'world': '7c211433f02071597741e6ff5a8ea34789abbf43'
      # 'hello': 'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d'
      # 'hi': 'c22b5f9178342609428d6f51b2c5af4c0bde6a42'
      # '1': '356a192b7913b04c54574d18c28d46e6395428ab'
      # '2': 'da4b9237bacccdf19c0760cab7aec4a8359010b0'
      # '3': '77de68daecd823babbb58edb1c8e14d7106e83bb'
      dict(
          testcase_name='string_feature_with_frequency_and_shuffle',
          x_data=[b'world', b'hello', b'hello'],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          expected_vocab_file_contents=[(b'world', 1), (b'hello', 2)],
          fingerprint_shuffle=True,
          store_frequency=True),
      dict(
          testcase_name='string_feature_with_frequency_and_no_shuffle',
          x_data=[b'hi', b'ho ho', b'ho ho'],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          expected_vocab_file_contents=[(b'ho ho', 2), (b'hi', 1)],
          store_frequency=True),
      dict(
          testcase_name='string_feature_with_no_frequency_and_shuffle',
          x_data=[b'world', b'hello', b'hello'],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          expected_vocab_file_contents=[b'world', b'hello'],
          fingerprint_shuffle=True),
      dict(
          testcase_name='string_feature_with_no_frequency_and_no_shuffle',
          x_data=[b'world', b'hello', b'hello'],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          expected_vocab_file_contents=[b'hello', b'world']),
      dict(
          testcase_name='int_feature_with_frequency_and_shuffle',
          x_data=[1, 2, 2, 3],
          x_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          expected_vocab_file_contents=[(b'1', 1), (b'3', 1), (b'2', 2)],
          fingerprint_shuffle=True,
          store_frequency=True),
      dict(
          testcase_name='int_feature_with_frequency_and_no_shuffle',
          x_data=[2, 1, 1, 1],
          x_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          expected_vocab_file_contents=[(b'1', 3), (b'2', 1)],
          store_frequency=True),
      dict(
          testcase_name='int_feature_with_no_frequency_and_shuffle',
          x_data=[1, 2, 2, 3],
          x_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          expected_vocab_file_contents=[b'1', b'3', b'2'],
          fingerprint_shuffle=True),
      dict(
          testcase_name='int_feature_with_no_frequency_and_no_shuffle',
          x_data=[1, 2, 2, 3],
          x_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          expected_vocab_file_contents=[b'2', b'3', b'1']),
  ] + _WITH_LABEL_PARAMS))
  def testVocabulary(self,
                     x_data,
                     x_feature_spec,
                     label_data=None,
                     label_feature_spec=None,
                     weight_data=None,
                     weight_feature_spec=None,
                     expected_vocab_file_contents=None,
                     **kwargs):
    """Test tft.Vocabulary with various inputs."""

    input_data = [{'x': x} for x in x_data]
    input_feature_spec = {'x': x_feature_spec}

    if label_data is not None:
      for idx, label in enumerate(label_data):
        input_data[idx]['label'] = label
      input_feature_spec['label'] = label_feature_spec

    if weight_data is not None:
      for idx, weight in enumerate(weight_data):
        input_data[idx]['weights'] = weight
      input_feature_spec['weights'] = weight_feature_spec

    input_metadata = tft_unit.metadata_from_feature_spec(input_feature_spec)

    def preprocessing_fn(inputs):
      x = inputs['x']
      labels = inputs.get('label')
      weights = inputs.get('weights')
      # Note even though the return value is not used, calling tft.vocabulary
      # will generate the vocabulary as a side effect, and since we have named
      # this vocabulary it can be looked up using public APIs.
      tft.vocabulary(
          x,
          labels=labels,
          weights=weights,
          vocab_filename='my_vocab',
          **kwargs)
      return inputs

    self.assertAnalyzeAndTransformResults(
        input_data,
        input_metadata,
        preprocessing_fn,
        input_data,  # expected output data is same as input data
        input_metadata,  # expected output metadata is ame as input metadata
        expected_vocab_file_contents={'my_vocab': expected_vocab_file_contents})

  def testJointVocabularyForMultipleFeatures(self):
    input_data = [{
        'a': 'hello',
        'b': 'world',
        'c': 'aaaaa'
    }, {
        'a': 'good',
        'b': '',
        'c': 'hello'
    }, {
        'a': 'goodbye',
        'b': 'hello',
        'c': '\n'
    }, {
        'a': ' ',
        'b': 'aaaaa',
        'c': 'bbbbb'
    }]
    input_metadata = tft_unit.metadata_from_feature_spec({
        'a': tf.io.FixedLenFeature([], tf.string),
        'b': tf.io.FixedLenFeature([], tf.string),
        'c': tf.io.FixedLenFeature([], tf.string)
    })
    vocab_filename = 'test_compute_and_apply_vocabulary'
    expected_metadata = tft_unit.metadata_from_feature_spec(
        {
            'index_a': tf.io.FixedLenFeature([], tf.int64),
            'index_b': tf.io.FixedLenFeature([], tf.int64),
        }, {
            'index_a': schema_pb2.IntDomain(min=-1, max=6, is_categorical=True),
            'index_b': schema_pb2.IntDomain(min=-1, max=6, is_categorical=True),
        })

    def preprocessing_fn(inputs):
      deferred_vocab_and_filename = tft.vocabulary(
          tf.concat([inputs['a'], inputs['b'], inputs['c']], 0),
          vocab_filename=vocab_filename)
      return {
          'index_a':
              tft.apply_vocabulary(inputs['a'], deferred_vocab_and_filename),
          'index_b':
              tft.apply_vocabulary(inputs['b'], deferred_vocab_and_filename)
      }

    expected_data = [
        # For tied frequencies, larger (lexicographic) items come first.
        # Index 5 corresponds to the word bbbbb.
        {
            'index_a': 0,
            'index_b': 2
        },
        {
            'index_a': 4,
            'index_b': -1
        },
        {
            'index_a': 3,
            'index_b': 0
        },
        {
            'index_a': 6,
            'index_b': 1
        }
    ]
    self.assertAnalyzeAndTransformResults(input_data, input_metadata,
                                          preprocessing_fn, expected_data,
                                          expected_metadata)

  # From testVocabularyAnalyzerEmptyVocab
  _EMPTY_VOCABULARY_PARAMS = tft_unit.cross_named_parameters(
      [
          dict(testcase_name='string',
               x_data=['a', 'b'],
               x_feature_spec=tf.io.FixedLenFeature([], tf.string)),
          dict(testcase_name='int64',
               x_data=[1, 2],
               x_feature_spec=tf.io.FixedLenFeature([], tf.int64)),
      ],
      [
          dict(testcase_name='empty_vocabulary',
               index_data=[-1, -1],
               index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
               index_domain=schema_pb2.IntDomain(min=-1, max=0,
                                                 is_categorical=True),
               frequency_threshold=5),
      ])

  @tft_unit.named_parameters(*([
      # NOTE: Since these tests are a refactoring of existing tests, each test
      # case parameter (or parameters where the original test was parameterized
      # or tested multiple calls to tft.compute_and_apply_vocabulary) has a
      # comment indicating the test case that it is based on.  This preserves
      # the ability to track the proveance of the test case parameters in the
      # git history.
      # TODO(KesterTong): Remove these annotations and the above comment.
      # From testVocabularyAnalyzerWithLabelsAndTopK
      dict(
          testcase_name='string_feature_with_label_top_2',
          x_data=[
              b'hello', b'hello', b'hello', b'goodbye', b'aaaaa', b'aaaaa',
              b'goodbye', b'goodbye', b'aaaaa', b'aaaaa', b'goodbye', b'goodbye'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_data=[-1, -1, -1, 0, 1, 1, 0, 0, 0, 1, 1, 0],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=1, is_categorical=True),
          top_k=2),
      dict(
          testcase_name='string_feature_with_label_top_1',
          x_data=[
              b'hello', b'hello', b'hello', b'goodbye', b'aaaaa', b'aaaaa',
              b'goodbye', b'goodbye', b'aaaaa', b'aaaaa', b'goodbye', b'goodbye'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_data=[-1, -1, -1, 0, -1, -1, 0, 0, 0, -1, -1, 0],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=0, is_categorical=True),
          top_k=1),
      dict(
          testcase_name='int_feature_with_label_top_2',
          x_data=[3, 3, 3, 1, 2, 2, 1, 1, 2, 2, 1, 1],
          x_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          label_data=[1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_data=[-1, -1, -1, 0, 1, 1, 0, 0, 0, 1, 1, 0],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=1, is_categorical=True),
          top_k=2),
      # From testVocabularyAnalyzerWithMultiDimensionalInputs
      dict(
          testcase_name='varlen_feature',
          x_data=[[b'world', b'hello', b'hello'], [b'hello', b'world', b'foo'],
                  [], [b'hello']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          index_data=[[1, 0, 0], [0, 1, -99], [], [0]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=1, is_categorical=True),
          default_value=-99,
          top_k=2),
      dict(
          testcase_name='vector_feature',
          x_data=[[b'world', b'hello', b'hello'], [b'hello', b'world', b'moo'],
                  [b'hello', b'hello', b'foo'], [b'world', b'foo', b'moo']],
          x_feature_spec=tf.io.FixedLenFeature([3], tf.string),
          index_data=[[1, 0, 0], [0, 1, -99], [0, 0, -99], [1, -99, -99]],
          index_feature_spec=tf.io.FixedLenFeature([3], tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=1, is_categorical=True),
          default_value=-99,
          top_k=2),
      dict(
          testcase_name='varlen_feature_with_labels',
          x_data=[[b'hello', b'world', b'bye', b'moo'],
                  [b'world', b'moo', b'foo'], [b'hello', b'foo', b'moo'],
                  [b'moo']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          label_data=[1, 0, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_data=[[0, -99, 1, -99], [-99, -99, -99], [0, -99, -99], [-99]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=1, is_categorical=True),
          default_value=-99,
          top_k=2),
      dict(
          testcase_name='vector_feature_with_labels',
          x_data=[[b'world', b'hello', b'hi'], [b'hello', b'world', b'moo'],
                  [b'hello', b'bye', b'foo'], [b'world', b'foo', b'moo']],
          x_feature_spec=tf.io.FixedLenFeature([3], tf.string),
          label_data=[1, 0, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_data=[[-99, -99, 1], [-99, -99, 0], [-99, -99, -99],
                      [-99, -99, 0]],
          index_feature_spec=tf.io.FixedLenFeature([3], tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=1, is_categorical=True),
          default_value=-99,
          top_k=2),
      dict(
          testcase_name='varlen_integer_feature_with_labels',
          x_data=[[0, 1, 3, 2], [1, 2, 4], [0, 4, 2], [2]],
          x_feature_spec=tf.io.VarLenFeature(tf.int64),
          label_data=[1, 0, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_data=[[0, -99, 1, -99], [-99, -99, -99], [0, -99, -99], [-99]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=1, is_categorical=True),
          default_value=-99,
          top_k=2),
      dict(
          testcase_name='varlen_feature_with_some_empty_feature_values',
          x_data=[[b'world', b'hello', b'hi', b'moo'], [],
                  [b'world', b'hello', b'foo'], []],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          label_data=[1, 0, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_data=[[0, 1, -99, -99], [], [0, 1, -99], []],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=1, is_categorical=True),
          default_value=-99,
          top_k=2),
      # From testSparseVocabularyWithMultiClassLabels
      dict(
          testcase_name='varlen_with_multiclass_labels',
          x_data=[[1, 2, 3, 5], [1, 4, 5], [1, 2], [1, 2], [1, 3, 5], [1, 4, 3],
                  [1, 3]],
          x_feature_spec=tf.io.VarLenFeature(tf.int64),
          label_data=[1, 0, 1, 1, 4, 5, 4],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_data=[[-1, 0, 2, 3], [-1, 1, 3], [-1, 0], [-1, 0], [-1, 2, 3],
                      [-1, 1, 2], [-1, 2]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=3, is_categorical=True),
          top_k=4),
      # From testVocabularyAnalyzerWithLabelsAndWeights
      dict(
          testcase_name='labels_and_weights',
          x_data=[
              b'hello', b'hello', b'hello', b'goodbye', b'aaaaa', b'aaaaa',
              b'goodbye', b'goodbye', b'aaaaa', b'aaaaa', b'goodbye', b'goodbye'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          weight_data=[
              0.3, 0.4, 0.3, 1.2, 0.6, 0.7, 1.0, 1.0, 0.6, 0.7, 1.0, 1.0
          ],
          weight_feature_spec=tf.io.FixedLenFeature([], tf.float32),
          index_data=[2, 2, 2, 1, 0, 0, 1, 1, 0, 0, 1, 1],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=2,
                                            is_categorical=True)),
      # From testVocabularyAnalyzerWithWeights
      dict(
          testcase_name='string_feature_with_weights',
          x_data=[
              b'hello', b'world', b'goodbye', b'aaaaa', b'aaaaa', b'goodbye'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          weight_data=[1.0, .5, 1.0, .26, .25, 1.5],
          weight_feature_spec=tf.io.FixedLenFeature([], tf.float32),
          index_data=[1, 3, 0, 2, 2, 0],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=3,
                                            is_categorical=True)),
      dict(
          testcase_name='int64_feature_with_weights',
          x_data=[2, 1, 3, 4, 4, 3],
          x_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          weight_data=[1.0, .5, 1.0, .26, .25, 1.5],
          weight_feature_spec=tf.io.FixedLenFeature([], tf.float32),
          index_data=[1, 3, 0, 2, 2, 0],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=3,
                                            is_categorical=True)),
      # From testVocabularyAnalyzer
      dict(
          testcase_name='whitespace_newlines_and_empty_strings',
          x_data=[
              b'hello', b'world', b'hello', b'hello', b'goodbye', b'world',
              b'aaaaa', b' ', b'', b'\n', b'hi \n ho \n', '\r'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          # The empty string and strings containing newlines map to default
          # value because the vocab cannot contain them.
          index_data=[0, 1, 0, 0, 2, 1, 3, 4, -1, -1, -1, -1],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=4,
                                            is_categorical=True)),
      # From testVocabularyAnalyzerOOV
      dict(
          testcase_name='whitespace_newlines_and_empty_strings_oov_buckets',
          x_data=[
              b'hello', b'world', b'hello', b'hello', b'goodbye', b'world',
              b'aaaaa', b' ', b'', b'\n', b'hi \n ho \n', '\r'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          # The empty string and strings containing newlines map to OOV because
          # the vocab cannot contain them.
          index_data=[0, 1, 0, 0, 2, 1, 3, 4, 5, 5, 5, 5],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=0, max=5, is_categorical=True),
          num_oov_buckets=1,
          vocab_filename='my_vocab',
          expected_vocab_file_contents={
              'my_vocab': [b'hello', b'world', b'goodbye', b'aaaaa', b' ']
          }),
      # From testVocabularyAnalyzerPositiveNegativeIntegers
      dict(
          testcase_name='positive_and_negative_integers',
          x_data=[13, 14, 13, 13, 12, 14, 11, 10, 10, -10, -10, -20],
          x_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_data=[0, 1, 0, 0, 4, 1, 5, 2, 2, 3, 3, 6],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=6, is_categorical=True),
          vocab_filename='my_vocab',
          expected_vocab_file_contents={
              'my_vocab': [b'13', b'14', b'10', b'-10', b'12', b'11', b'-20']
          }),
      # From testVocabularyAnalyzerWithNDInputs
      dict(
          testcase_name='rank_2',
          x_data=[[[b'some', b'say'], [b'the', b'world']],
                  [[b'will', b'end'], [b'in', b'fire']],
                  [[b'some', b'say'], [b'in', b'ice']]],
          x_feature_spec=tf.io.FixedLenFeature([2, 2], tf.string),
          index_data=[[[0, 1], [5, 3]], [[4, 8], [2, 7]], [[0, 1], [2, 6]]],
          index_feature_spec=tf.io.FixedLenFeature([2, 2], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=8,
                                            is_categorical=True)),
      # From testVocabularyAnalyzerWithTopK
      dict(
          testcase_name='top_k',
          x_data=[[b'hello', b'hello', b'world'],
                  [b'hello', b'goodbye', b'world'],
                  [b'hello', b'goodbye', b'foo']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          index_data=[[0, 0, 1], [0, -99, 1], [0, -99, -99]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=1, is_categorical=True),
          default_value=-99,
          top_k=2),
      dict(
          testcase_name='top_k_specified_as_str',
          x_data=[[b'hello', b'hello', b'world'],
                  [b'hello', b'goodbye', b'world'],
                  [b'hello', b'goodbye', b'foo']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          index_data=[[0, 0, 1], [0, -9, 1], [0, -9, -9]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(min=-9, max=1, is_categorical=True),
          default_value=-9,
          top_k='2'),
      # From testVocabularyAnalyzerWithFrequencyThreshold
      dict(
          testcase_name='frequency_threshold',
          x_data=[[b'hello', b'hello', b'world'],
                  [b'hello', b'goodbye', b'world'],
                  [b'hello', b'goodbye', b'foo']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          index_data=[[0, 0, 1], [0, 2, 1], [0, 2, -99]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=2, is_categorical=True),
          default_value=-99,
          frequency_threshold=2),
      dict(
          testcase_name='frequency_threshold_specified_with_str',
          x_data=[[b'hello', b'hello', b'world'],
                  [b'hello', b'goodbye', b'world'],
                  [b'hello', b'goodbye', b'foo']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          index_data=[[0, 0, 1], [0, 2, 1], [0, 2, -9]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(min=-9, max=2, is_categorical=True),
          default_value=-9,
          frequency_threshold='2'),
      # From testVocabularyAnalyzerWithFrequencyThresholdTooHigh
      dict(
          testcase_name='empty_vocabulary_from_high_frequency_threshold',
          x_data=[[b'hello', b'hello', b'world'],
                  [b'hello', b'goodbye', b'world'],
                  [b'hello', b'goodbye', b'foo']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          index_data=[[-99, -99, -99], [-99, -99, -99], [-99, -99, -99]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=0, is_categorical=True),
          default_value=-99,
          frequency_threshold=77),
      # From testVocabularyAnalyzerWithHighFrequencyThresholdAndOOVBuckets
      dict(
          testcase_name='top_k_and_oov',
          x_data=[[b'hello', b'hello', b'world', b'world'],
                  [b'hello', b'tarkus', b'toccata'],
                  [b'hello', b'goodbye', b'foo']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          # Generated vocab (ordered by frequency, then value) should be:
          # ["hello", "world", "goodbye", "foo", "tarkus", "toccata"]. After
          # applying top_k =1 this becomes ["hello"] plus three OOV buckets.
          # The specific output values here depend on the hash of the words,
          # and the test will break if the hash changes.
          index_data=[[0, 0, 2, 2], [0, 3, 1], [0, 2, 1]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(min=0, max=3, is_categorical=True),
          default_value=-99,
          top_k=1,
          num_oov_buckets=3),
      # From testVocabularyAnalyzerWithKeyFn
      dict(
          testcase_name='key_fn',
          x_data=[['a_X_1', 'a_X_1', 'a_X_2', 'b_X_1', 'b_X_2'],
                  ['a_X_1', 'a_X_1', 'a_X_2', 'a_X_2'], ['b_X_2']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          index_data=[[0, 0, 1, -99, 2], [0, 0, 1, 1], [2]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=2, is_categorical=True),
          coverage_top_k=1,
          default_value=-99,
          key_fn=lambda s: s.split(b'_X_')[0],
          frequency_threshold=3),
      # from testVocabularyAnalyzerWithKeyFnAndMultiCoverageTopK
      dict(
          testcase_name='key_fn_and_multi_coverage_top_k',
          x_data=[['a_X_1', 'a_X_1', 'a_X_2', 'b_X_1', 'b_X_2'],
                  ['a_X_1', 'a_X_1', 'a_X_2', 'a_X_2', 'a_X_3'], ['b_X_2']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          index_data=[[0, 0, 1, 3, 2], [0, 0, 1, 1, -99], [2]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=3, is_categorical=True),
          coverage_top_k=2,
          default_value=-99,
          key_fn=lambda s: s.split(b'_X_')[0],
          frequency_threshold=300),
      # from testVocabularyAnalyzerWithKeyFnAndTopK
      dict(
          testcase_name='key_fn_and_top_k',
          x_data=[['a_X_1', 'a_X_1', 'a_X_2', 'b_X_1', 'b_X_2'],
                  ['a_X_1', 'a_X_1', 'a_X_2', 'a_X_2'],
                  ['b_X_2', 'b_X_2', 'b_X_2', 'b_X_2', 'c_X_1']],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          index_data=[[1, 1, -99, -99, 0], [1, 1, -99, -99], [0, 0, 0, 0, 2]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=2, is_categorical=True),
          coverage_top_k=1,
          default_value=-99,
          key_fn=lambda s: s.split(b'_X_')[0],
          top_k=2),
      # from testVocabularyAnalyzerWithKeyFnMultiCoverageTopK
      dict(
          testcase_name='key_fn_multi_coverage_top_k',
          x_data=[
              ['0_X_a', '0_X_a', '5_X_a', '6_X_a', '6_X_a', '0_X_a'],
              ['0_X_a', '2_X_a', '2_X_a', '2_X_a', '0_X_a', '5_X_a'],
              ['1_X_b', '1_X_b', '3_X_b', '3_X_b', '0_X_b', '1_X_b', '1_X_b']
          ],
          x_feature_spec=tf.io.VarLenFeature(tf.string),
          index_data=[[0, 0, -99, -99, -99, 0], [0, 2, 2, 2, 0, -99],
                      [1, 1, 3, 3, -99, 1, 1]],
          index_feature_spec=tf.io.VarLenFeature(tf.int64),
          index_domain=schema_pb2.IntDomain(
              min=-99, max=3, is_categorical=True),
          coverage_top_k=2,
          default_value=-99,
          key_fn=lambda s: s.split(b'_X_')[1],
          frequency_threshold=4),
      # from testVocabularyAnalyzerWithKeyFnAndLabels
      dict(
          testcase_name='key_fn_and_labels',
          x_data=[
              'aaa', 'aaa', 'aaa', 'aab', 'aba', 'aba', 'aab', 'aab', 'aba',
              'abc', 'abc', 'aab'
          ],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          label_data=[1, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 0],
          label_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_data=[0, 0, 0, -1, -1, -1, -1, -1, -1, 1, 1, -1],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=1, is_categorical=True),
          coverage_top_k=1,
          key_fn=lambda s: s[:2],
          frequency_threshold=3),
      # from testVocabularyAnalyzerWithKeyFnAndWeights
      dict(
          testcase_name='key_fn_and_weights',
          x_data=['xa', 'xa', 'xb', 'ya', 'yb', 'yc'],
          x_feature_spec=tf.io.FixedLenFeature([], tf.string),
          weight_data=[1.0, 0.5, 3.0, 0.6, 0.25, 0.5],
          weight_feature_spec=tf.io.FixedLenFeature([], tf.float32),
          index_data=[1, 1, 0, -1, -1, -1],
          index_feature_spec=tf.io.FixedLenFeature([], tf.int64),
          index_domain=schema_pb2.IntDomain(min=-1, max=1, is_categorical=True),
          coverage_top_k=1,
          key_fn=lambda s: s[0],
          frequency_threshold=1.5,
          coverage_frequency_threshold=1),
  ] + _EMPTY_VOCABULARY_PARAMS))
  def testComputeAndApplyVocabulary(
      self, x_data, x_feature_spec, index_data, index_feature_spec,
      index_domain, label_data=None, label_feature_spec=None,
      weight_data=None, weight_feature_spec=None,
      expected_vocab_file_contents=None, **kwargs):
    """Test tft.compute_and_apply_vocabulary with various inputs."""

    input_data = [{'x': x} for x in x_data]
    input_feature_spec = {'x': x_feature_spec}
    expected_data = [{'index': index} for index in index_data]
    expected_feature_spec = {'index': index_feature_spec}
    expected_domains = {'index': index_domain}

    if label_data is not None:
      for idx, label in enumerate(label_data):
        input_data[idx]['label'] = label
      input_feature_spec['label'] = label_feature_spec

    if weight_data is not None:
      for idx, weight in enumerate(weight_data):
        input_data[idx]['weights'] = weight
      input_feature_spec['weights'] = weight_feature_spec

    input_metadata = tft_unit.metadata_from_feature_spec(input_feature_spec)
    expected_metadata = tft_unit.metadata_from_feature_spec(
        expected_feature_spec, expected_domains)

    def preprocessing_fn(inputs):
      x = inputs['x']
      labels = inputs.get('label')
      weights = inputs.get('weights')
      index = tft.compute_and_apply_vocabulary(
          x, labels=labels, weights=weights, **kwargs)
      return {'index': index}

    self.assertAnalyzeAndTransformResults(
        input_data,
        input_metadata,
        preprocessing_fn,
        expected_data,
        expected_metadata,
        expected_vocab_file_contents=expected_vocab_file_contents)

  # Example on how to use the vocab frequency as part of the transform
  # function.
  def testCreateVocabWithFrequency(self):
    input_data = [
        {'a': 'hello', 'b': 'world', 'c': 'aaaaa'},
        {'a': 'good', 'b': '', 'c': 'hello'},
        {'a': 'goodbye', 'b': 'hello', 'c': '\n'},
        {'a': '_', 'b': 'aaaaa', 'c': 'bbbbb'}
    ]
    input_metadata = tft_unit.metadata_from_feature_spec({
        'a': tf.io.FixedLenFeature([], tf.string),
        'b': tf.io.FixedLenFeature([], tf.string),
        'c': tf.io.FixedLenFeature([], tf.string)
    })
    vocab_filename = 'test_vocab_with_frequency'
    expected_metadata = tft_unit.metadata_from_feature_spec({
        'index_a': tf.io.FixedLenFeature([], tf.int64),
        'index_b': tf.io.FixedLenFeature([], tf.int64),
        'frequency_a': tf.io.FixedLenFeature([], tf.int64),
        'frequency_b': tf.io.FixedLenFeature([], tf.int64),
    }, {
        'index_a': schema_pb2.IntDomain(min=-1, max=6, is_categorical=True),
        'index_b': schema_pb2.IntDomain(min=-1, max=6, is_categorical=True),
        'frequency_a': schema_pb2.IntDomain(min=-1, max=6, is_categorical=True),
        'frequency_b': schema_pb2.IntDomain(min=-1, max=6, is_categorical=True),
    })

    def preprocessing_fn(inputs):
      deferred_vocab_and_filename = tft.vocabulary(
          tf.concat([inputs['a'], inputs['b'], inputs['c']], 0),
          vocab_filename=vocab_filename,
          store_frequency=True)

      def _apply_vocab(y, deferred_vocab_filename_tensor):
        # NOTE: Please be aware that TextFileInitializer assigns a special
        # meaning to the constant tf.lookup.TextFileIndex.LINE_NUMBER.
        table = tf.lookup.StaticHashTable(
            tf.lookup.TextFileInitializer(
                deferred_vocab_filename_tensor,
                tf.string,
                1,
                tf.int64,
                tf.lookup.TextFileIndex.LINE_NUMBER,
                delimiter=' '),
            default_value=-1)
        table_size = table.size()
        return table.lookup(y), table_size

      def _apply_frequency(y, deferred_vocab_filename_tensor):
        table = tf.lookup.StaticHashTable(
            tf.lookup.TextFileInitializer(
                deferred_vocab_filename_tensor,
                tf.string,
                1,
                tf.int64,
                0,
                delimiter=' '),
            default_value=-1)
        table_size = table.size()
        return table.lookup(y), table_size

      return {
          'index_a':
              tft.apply_vocabulary(
                  inputs['a'],
                  deferred_vocab_and_filename,
                  lookup_fn=_apply_vocab),
          'frequency_a':
              tft.apply_vocabulary(
                  inputs['a'],
                  deferred_vocab_and_filename,
                  lookup_fn=_apply_frequency),
          'index_b':
              tft.apply_vocabulary(
                  inputs['b'],
                  deferred_vocab_and_filename,
                  lookup_fn=_apply_vocab),
          'frequency_b':
              tft.apply_vocabulary(
                  inputs['b'],
                  deferred_vocab_and_filename,
                  lookup_fn=_apply_frequency),
      }

    expected_data = [
        # For tied frequencies, larger (lexicographic) items come first.
        # Index 5 corresponds to the word bbbbb.
        {'index_a': 0, 'frequency_a': 3, 'index_b': 2, 'frequency_b': 1},
        {'index_a': 4, 'frequency_a': 1, 'index_b': -1, 'frequency_b': -1},
        {'index_a': 3, 'frequency_a': 1, 'index_b': 0, 'frequency_b': 3},
        {'index_a': 6, 'frequency_a': 1, 'index_b': 1, 'frequency_b': 2}
    ]
    self.assertAnalyzeAndTransformResults(input_data, input_metadata,
                                          preprocessing_fn, expected_data,
                                          expected_metadata)

  def testVocabularyAnalyzerWithTokenization(self):
    def preprocessing_fn(inputs):
      return {
          'index':
              tft.compute_and_apply_vocabulary(
                  tf.compat.v1.strings.split(inputs['a']))
      }

    input_data = [{'a': 'hello hello world'}, {'a': 'hello goodbye world'}]
    input_metadata = tft_unit.metadata_from_feature_spec(
        {'a': tf.io.FixedLenFeature([], tf.string)})
    expected_data = [{'index': [0, 0, 1]}, {'index': [0, 2, 1]}]

    expected_metadata = tft_unit.metadata_from_feature_spec({
        'index': tf.io.VarLenFeature(tf.int64),
    }, {
        'index': schema_pb2.IntDomain(min=-1, max=2, is_categorical=True),
    })
    self.assertAnalyzeAndTransformResults(input_data, input_metadata,
                                          preprocessing_fn, expected_data,
                                          expected_metadata)

  def testPipelineWithoutAutomaterialization(self):
    # Other tests pass lists instead of PCollections and thus invoke
    # automaterialization where each call to a beam PTransform will implicitly
    # run its own pipeline.
    #
    # In order to test the case where PCollections are not materialized in
    # between calls to the tf.Transform PTransforms, we include a test that is
    # not based on automaterialization.
    def preprocessing_fn(inputs):
      return {'x_scaled': tft.scale_to_0_1(inputs['x'])}

    def equal_to(expected):

      def _equal(actual):
        dict_key_fn = lambda d: sorted(d.items())
        sorted_expected = sorted(expected, key=dict_key_fn)
        sorted_actual = sorted(actual, key=dict_key_fn)
        if sorted_expected != sorted_actual:
          raise ValueError('Failed assert: %s == %s' % (expected, actual))
      return _equal

    with self._makeTestPipeline() as pipeline:
      input_data = pipeline | 'CreateTrainingData' >> beam.Create(
          [{'x': 4}, {'x': 1}, {'x': 5}, {'x': 2}])
      metadata = tft_unit.metadata_from_feature_spec(
          {'x': tf.io.FixedLenFeature([], tf.float32)})
      with beam_impl.Context(temp_dir=self.get_temp_dir()):
        transform_fn = (
            (input_data, metadata)
            | 'AnalyzeDataset' >> beam_impl.AnalyzeDataset(preprocessing_fn))

        # Run transform_columns on some eval dataset.
        eval_data = pipeline | 'CreateEvalData' >> beam.Create(
            [{'x': 6}, {'x': 3}])
        transformed_eval_data, _ = (
            ((eval_data, metadata), transform_fn)
            | 'TransformDataset' >> beam_impl.TransformDataset())
        expected_data = [{'x_scaled': 1.25}, {'x_scaled': 0.5}]
        beam_test_util.assert_that(
            transformed_eval_data, equal_to(expected_data))

  def testVocabularyWithFrequency(self):
    outfile = 'vocabulary_with_frequency'
    def preprocessing_fn(inputs):

      # Force the analyzer to be executed, and store the frequency file as a
      # side-effect.
      _ = tft.vocabulary(
          inputs['a'], vocab_filename=outfile, store_frequency=True)
      _ = tft.vocabulary(inputs['a'], store_frequency=True)
      _ = tft.vocabulary(inputs['b'], store_frequency=True)

      # The following must not produce frequency output, just the vocab words.
      _ = tft.vocabulary(inputs['b'])
      a_int = tft.compute_and_apply_vocabulary(inputs['a'])

      # Return input unchanged, this preprocessing_fn is a no-op except for
      # computing uniques.
      return {'a_int': a_int}

    def check_asset_file_contents(assets_path, filename, expected):
      assets_file = os.path.join(assets_path, filename)
      with tf.io.gfile.GFile(assets_file, 'r') as f:
        contents = f.read()

      self.assertMultiLineEqual(expected, contents)

    input_metadata = tft_unit.metadata_from_feature_spec({
        'a': tf.io.FixedLenFeature([], tf.string),
        'b': tf.io.FixedLenFeature([], tf.string)
    })

    tft_tmp_dir = os.path.join(self.get_temp_dir(), 'temp_dir')
    transform_fn_dir = os.path.join(self.get_temp_dir(), 'export_transform_fn')

    with beam_impl.Context(temp_dir=tft_tmp_dir):
      with self._makeTestPipeline() as pipeline:
        input_data = pipeline | beam.Create([
            {'a': 'hello', 'b': 'hi'},
            {'a': 'world', 'b': 'ho ho'},
            {'a': 'hello', 'b': 'ho ho'},
        ])
        transform_fn = (
            (input_data, input_metadata)
            | beam_impl.AnalyzeDataset(preprocessing_fn))
        _ = transform_fn | transform_fn_io.WriteTransformFn(transform_fn_dir)

    self.assertTrue(os.path.isdir(tft_tmp_dir))

    saved_model_path = os.path.join(transform_fn_dir,
                                    tft.TFTransformOutput.TRANSFORM_FN_DIR)
    assets_path = os.path.join(saved_model_path,
                               tf.saved_model.ASSETS_DIRECTORY)
    self.assertTrue(os.path.isdir(assets_path))
    six.assertCountEqual(self, [
        outfile, 'vocab_frequency_vocabulary_1', 'vocab_frequency_vocabulary_2',
        'vocab_compute_and_apply_vocabulary_vocabulary', 'vocab_vocabulary_3'
    ], os.listdir(assets_path))

    check_asset_file_contents(assets_path, outfile,
                              '2 hello\n1 world\n')

    check_asset_file_contents(assets_path, 'vocab_frequency_vocabulary_1',
                              '2 hello\n1 world\n')

    check_asset_file_contents(assets_path, 'vocab_frequency_vocabulary_2',
                              '2 ho ho\n1 hi\n')

    check_asset_file_contents(assets_path, 'vocab_vocabulary_3',
                              'ho ho\nhi\n')

    check_asset_file_contents(assets_path,
                              'vocab_compute_and_apply_vocabulary_vocabulary',
                              'hello\nworld\n')

  def testVocabularyWithKeyFnAndFrequency(self):
    def key_fn(string):
      return string.split(b'_X_')[1]

    outfile = 'vocabulary_with_frequency'

    def preprocessing_fn(inputs):

      # Force the analyzer to be executed, and store the frequency file as a
      # side-effect.

      _ = tft.vocabulary(
          tf.compat.v1.strings.split(inputs['a']),
          coverage_top_k=1,
          key_fn=key_fn,
          frequency_threshold=4,
          vocab_filename=outfile,
          store_frequency=True)

      _ = tft.vocabulary(
          tf.compat.v1.strings.split(inputs['a']),
          coverage_top_k=1,
          key_fn=key_fn,
          frequency_threshold=4,
          store_frequency=True)

      a_int = tft.compute_and_apply_vocabulary(
          tf.compat.v1.strings.split(inputs['a']),
          coverage_top_k=1,
          key_fn=key_fn,
          frequency_threshold=4)

      # Return input unchanged, this preprocessing_fn is a no-op except for
      # computing uniques.
      return {'a_int': a_int}

    def check_asset_file_contents(assets_path, filename, expected):
      assets_file = os.path.join(assets_path, filename)
      with tf.io.gfile.GFile(assets_file, 'r') as f:
        contents = f.read()

      self.assertMultiLineEqual(expected, contents)

    input_metadata = tft_unit.metadata_from_feature_spec(
        {'a': tf.io.FixedLenFeature([], tf.string)})

    tft_tmp_dir = os.path.join(self.get_temp_dir(), 'temp_dir')
    transform_fn_dir = os.path.join(self.get_temp_dir(), 'export_transform_fn')

    with beam_impl.Context(temp_dir=tft_tmp_dir):
      with self._makeTestPipeline() as pipeline:
        input_data = pipeline | beam.Create([
            {'a': '1_X_a 1_X_a 2_X_a 1_X_b 2_X_b'},
            {'a': '1_X_a 1_X_a 2_X_a 2_X_a'},
            {'a': '2_X_b 3_X_c 4_X_c'}
        ])
        transform_fn = (
            (input_data, input_metadata)
            | beam_impl.AnalyzeDataset(preprocessing_fn))
        _ = transform_fn | transform_fn_io.WriteTransformFn(transform_fn_dir)

    self.assertTrue(os.path.isdir(tft_tmp_dir))

    saved_model_path = os.path.join(transform_fn_dir,
                                    tft.TFTransformOutput.TRANSFORM_FN_DIR)
    assets_path = os.path.join(saved_model_path,
                               tf.saved_model.ASSETS_DIRECTORY)
    self.assertTrue(os.path.isdir(assets_path))

    check_asset_file_contents(assets_path, outfile,
                              '4 1_X_a\n2 2_X_b\n1 4_X_c\n')


if __name__ == '__main__':
  tft_unit.main()
