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


def run_bo(expt_info, data, target, opt_type="MAX", batch_size=2):
    variable_type_dict = pd.read_json(expt_info.variable_dict)
    baybe_paramter_list = []
    for col in variable_type_dict.columns:
        df = variable_type_dict[col].T
        if df['parameter-type'] == 'subs':
            baybe_paramter_list.append(
                SubstanceParameter(f"{col}", data=data, encoding=f"{df['encoding'].upper()}")
            )
        elif df['parameter-type'] == "cat":
            baybe_paramter_list.append(
                CategoricalParameter(f"{col}", values=data, encoding="OHE")
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

    objective = Objective(mode="SINGLE", targets=[NumericalTarget(name=target, mode=f"{opt_type}")])

    recommender = TwoPhaseMetaRecommender(
        initial_recommender=RandomRecommender(),
        recommender=SequentialGreedyRecommender(
            surrogate_model=GaussianProcessSurrogate(),
            acquisition_function_cls=f"{expt_info.acqFuncType}",
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