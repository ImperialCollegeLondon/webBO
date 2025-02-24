from baybe import Campaign
from baybe.objective import Objective
from baybe.parameters import CategoricalParameter, NumericalContinuousParameter, NumericalDiscreteParameter, SubstanceParameter
from baybe.searchspace import SearchSpace
from baybe.targets import NumericalTarget
from baybe.recommenders import RandomRecommender, SequentialGreedyRecommender, TwoPhaseMetaRecommender
from baybe.surrogates import GaussianProcessSurrogate
from baybe.utils.dataframe import add_fake_results
import pandas as pd
import numpy as np


def rerun_bo(campaign_db_entry, new_measurements, batch_size=1):
    campaign = Campaign.from_json(campaign_db_entry.campaign_info)
    campaign.add_measurements(new_measurements)
    return campaign.recommend(batch_size=batch_size)


def run_bo(expt_info, target, opt_type, batch_size=1):
    variable_type_dict = pd.read_json(expt_info.variables)
    baybe_paramter_list = []
    target = target[0]
    opt_type = opt_type[0]
    print('target:',target, 'opt type', opt_type)

    columns = list(variable_type_dict.keys())
    target_name = columns[int(target)]
    for col in variable_type_dict.columns:
        df = variable_type_dict[col].T
        if df['parameter-type'] == 'subs':
            baybe_paramter_list.append(
                SubstanceParameter(f"{col}", data=df['json'], encoding=f"{df['encoding']}")
            )
        elif df['parameter-type'] == "cat":
            baybe_paramter_list.append(
                CategoricalParameter(f"{col}", values=pd.read_json(df['json'])[f'{col}'], encoding="OHE")
            )
        elif df['parameter-type'] == 'int':
            baybe_paramter_list.append(
                NumericalDiscreteParameter(f"{col}", values=list(np.arange(int(df['min']), int(df['max']), 1.0)))
            )
        else:
            baybe_paramter_list.append(
                NumericalContinuousParameter(f"{col}", bounds=(float(df['min']), float(df['max'])))
            )
    search_space = SearchSpace.from_product(baybe_paramter_list)

    objective = Objective(mode="SINGLE", targets=[NumericalTarget(name=target_name, mode=f"{opt_type}", bounds=[variable_type_dict[target_name]["min"],variable_type_dict[target_name]["max"]], transformation='LINEAR')])

    recommender = TwoPhaseMetaRecommender(
        initial_recommender=RandomRecommender(),
        recommender=SequentialGreedyRecommender(
            surrogate_model=GaussianProcessSurrogate(),
            acquisition_function_cls=f"{expt_info.acqFunc}",
            allow_repeated_recommendations=False,
            allow_recommending_already_measured=False,
        )
    )

    campaign = Campaign(
        searchspace=search_space,
        recommender=recommender,
        objective=objective,
    )

    return campaign.recommend(batch_size=batch_size), campaign


def run_mobo(expt_info, targets,  opt_types, weights, batch_size=1):
    variable_type_dict = pd.read_json(expt_info.variables)
    baybe_parameter_list = []
    columns = list(variable_type_dict.keys())
    targets_arr = []
    

    for i in range(len(targets)):
        target = targets[i] 
        opt_type = opt_types[i]  
        target_name = columns[int(target)] 
        

        
        numerical_target = NumericalTarget(
            name=target_name,
            mode=f"{opt_type}",  
            bounds=[variable_type_dict[target_name]["min"], variable_type_dict[target_name]["max"]],
            transformation='LINEAR'

        )

        targets_arr.append(numerical_target)

    for col in variable_type_dict.columns:
        df = variable_type_dict[col].T
        if df['parameter-type'] == 'subs':
            baybe_parameter_list.append(
                SubstanceParameter(f"{col}", data=df['json'], encoding=f"{df['encoding']}")
            )
        elif df['parameter-type'] == "cat":
            baybe_parameter_list.append(
                CategoricalParameter(f"{col}", values=pd.read_json(df['json'])[f'{col}'], encoding="OHE")
            )
        elif df['parameter-type'] == 'int':
            baybe_parameter_list.append(
                NumericalDiscreteParameter(f"{col}", values=list(np.arange(int(df['min']), int(df['max']), 1.0)))
            )
        else:
            baybe_parameter_list.append(
                NumericalContinuousParameter(f"{col}", bounds=(float(df['min']), float(df['max'])))
            )

    print(targets_arr)
    search_space = SearchSpace.from_product(baybe_parameter_list)
    objective = Objective(mode="DESIRABILITY",targets=targets_arr, weights=weights, combine_func="GEOM_MEAN")

    recommender = TwoPhaseMetaRecommender(
        initial_recommender=RandomRecommender(),
        recommender=SequentialGreedyRecommender(
            surrogate_model=GaussianProcessSurrogate(),
            acquisition_function_cls=f"{expt_info.acqFunc}",
            allow_repeated_recommendations=False,
            allow_recommending_already_measured=False,
        )
    )

    campaign = Campaign(
        searchspace=search_space,
        recommender=recommender,
        objective=objective,
    )

    return campaign.recommend(batch_size=batch_size), campaign