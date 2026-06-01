import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ab_test_platform import ABTestPlatform, ABTestExperiment


class TestABTestPlatform:
    
    def setup_method(self):
        # 使用正确的mock_data路径
        mock_data_dir = os.path.join(os.path.dirname(__file__), '..', 'mock_data')
        self.ab_platform = ABTestPlatform(data_dir=mock_data_dir)
    
    def test_create_experiment(self):
        experiment = self.ab_platform.create_experiment(
            name='Test Experiment',
            description='Test description',
            variants=[
                {"id": "control", "name": "对照组", "is_control": True},
                {"id": "variant_a", "name": "实验组A", "is_control": False}
            ],
            traffic_allocation=0.5
        )
        assert isinstance(experiment, ABTestExperiment)
        assert experiment.name == 'Test Experiment'
    
    def test_experiment_is_user_eligible(self):
        experiment = ABTestExperiment(
            experiment_id='test_exp',
            name='Test',
            variants=[
                {"id": "control", "name": "对照组", "is_control": True}
            ],
            filters={
                "regions": ["CN"],
                "platforms": ["ios"]
            }
        )
        user_info = {'user_id': 'user123', 'region': 'CN', 'platform': 'ios'}
        result = experiment.is_user_eligible(user_info)
        assert result is True
        
        user_info_ineligible = {'user_id': 'user456', 'region': 'US', 'platform': 'ios'}
        result = experiment.is_user_eligible(user_info_ineligible)
        assert result is False