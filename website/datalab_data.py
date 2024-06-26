import pandas as pd
import os
from datalab_api import DatalabClient
from io import StringIO
import re
import lxml  # lxml has to be installed to process tables, this is just to check if it is installed
import random, string
from datetime import datetime

class DatalabData:
    """Class to retrieve and handle data from Datalab

    Parameters:
        api_key (str): the api key for the Datalab API
        domain (str): the domain of the Datalab instance
        collection_id (str): the collection id of the data to be retrieved or uploaded
        blocktype (str): the blocktype of the data to be retrieved
        features (list): the features of the data to create csv table for BO

    Example usage:
    >>> # retrieve data from Datalab
    >>> retrieve_data = DatalabData(api_key, domain, collection_id, blocktype, features)
    >>> data_dataframe = retrieve_data.get_data()
    >>> # upload data to Datalab
    >>> upload_data = DatalabData(api_key, domain, collection_id)
    >>> upload_data.create_new_samples(data_dataframe)
    """

    def __init__(self, api_key, domain, collection_id, blocktype=None, features=None):
        self.api_key = api_key
        self.domain = domain
        self.collection_id = collection_id
        if blocktype is not None:
            self.blocktype = blocktype
        if features is not None:    
            self.features = features
        os.environ["DATALAB_API_KEY"] = api_key
        self.client = DatalabClient(domain)

    def get_items_from_collection(self, collection_id):
        # gets all the item ids from a collection
        samples = self.client.get_items()
        collection_samples_id = []
        for sample in samples:
            for collection in sample["collections"]:
                if collection["collection_id"] == collection_id:
                    collection_samples_id.append(sample["item_id"])
        return collection_samples_id

    def check_for_block(self, item, blocktype):
        # checks if a block of a certain type exists in an item
        for block in item["blocks_obj"].values():
            if block["blocktype"] == blocktype:
                return True
        return False

    def get_block_id(self, item, blocktype):
        # gets the block id of a block of a certain type in an item
        for block in item["blocks_obj"].values():
            if block["blocktype"] == blocktype:
                return block["block_id"]
        return None

    def get_table_from_block(self, item_id, blocktype):
        # gets the freeform comment of a block of a certain type in an item and returns it as string
        # if block missing creates a block of the specified type
        item = self.client.get_item(item_id, load_blocks=True)
        if self.check_for_block(item, blocktype):
            block_id = self.get_block_id(item, blocktype)
            if "freeform_comment" in item["blocks_obj"][block_id].keys():
                block_text = item["blocks_obj"][block_id]["freeform_comment"]
                return block_text
        else:
            file_id = item["file_ObjectIds"][
                0
            ]  # assuming the first file is the correct one, will need to change this
            self.client.create_data_block(item_id, blocktype, file_id)
            self.client = DatalabClient(
                self.domain
            )  # need to reinitialize the client to get the new block
            item = self.client.get_item(item_id, load_blocks=True)
            block_id = self.get_block_id(item, blocktype)
            if block_id is not None:
                if "freeform_comment" in item["blocks_obj"][block_id].keys():
                    block_text = item["blocks_obj"][block_id]["freeform_comment"]
                    return block_text
            return None
        return None

    def get_tables_from_collection(self, collection_id, blocktype):
        # gets the freeform comment of a block of a certain type in all items in a collection
        collection_samples_id = self.get_items_from_collection(collection_id)
        tables = []
        for sample_id in collection_samples_id:
            table = self.get_table_from_block(sample_id, blocktype)
            if table is not None:
                tables.append(table)
        return tables

    def create_dataframe_from_html(self, html):
        # creates a pandas dataframe from a string of html tables
        table_regex = r"<table[^>]*>(.*?)</table>"
        html = " ".join(html)
        tables = re.findall(table_regex, html, flags=re.IGNORECASE | re.DOTALL)
        if len(tables) == 0:  # check if there are any tables in the html
            return None
        all_df = pd.read_html(StringIO(html), header=0, flavor="lxml")
        return all_df

    def df_transpose(self, df):
        # function that transposes the parameter, value table to dataframe with parameters as headers
        df = df.transpose().reset_index()
        df.drop("index", axis=1, inplace=True)
        df.columns = df.iloc[0]
        df = df[1:]
        return df

    def make_table(self, df_list, features):
        new_df = pd.DataFrame(columns=features)
        for df in df_list:
            df = self.df_transpose(df)
            df = df[features]
            new_df = pd.concat([new_df, df]).reset_index(drop=True)
        return new_df

    def get_data(self):
        # gets the data from the Datalab instance
        tables = self.get_tables_from_collection(self.collection_id, self.blocktype)
        df_list = self.create_dataframe_from_html(tables)
        if df_list is None:
            raise ValueError(
                "No tables found in blocktype {} for collection {}".format(
                    self.blocktype, self.collection_id
                )
            )
        try:
            data = self.make_table(df_list, self.features)
        except KeyError:
            raise KeyError(
                "Error in creating dataframe from tables, check if parameter names are correct or missing"
            )
        return data
    
    def make_param_val_table(self, df):
        df = df.transpose().reset_index()
        new_iterations = df.columns[1:]
        html_tables = []
        for iteration in new_iterations:
            if iteration is int:
                new_df = pd.DataFrame(columns=['Parameter', 'Value'])
                new_df['Parameter'] = df['index']
                new_df['Value'] = df[iteration]
                html_tables.append(new_df.to_html(border=1, index=False))
        return html_tables
    
    def randomword(self, length):
        letters = string.ascii_uppercase
        return ''.join(random.choice(letters) for i in range(length))
    
    def create_new_samples(self, df):
        # creates new samples in the Datalab instance from a dataframe
        # the collection where data is uploaded needs to be made in datalab beforehand
        html_tables = self.make_param_val_table(df)
        for i, tab in enumerate(html_tables):
            new_data = {'collections': [{'collection_id': self.collection_id}],
                        'synthesis_description': tab,
                        'description': 'Experimental suggestion from webBO',
                        'name': f'WebBO suggestion {i+1}',  # change name to something more descriptive
                        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:00")
                        }
            sample_id = self.randomword(4)+'_webBO'
            try:
                self.client.create_item(sample_id, 'samples', new_data)   
            except RuntimeError:
                raise RuntimeError('Error in creating new samples, check if collection exists on Datalab instance or data is correct')