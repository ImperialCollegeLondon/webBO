import pandas as pd
import os
from datalab_api import DatalabClient
from io import StringIO
import re
import lxml  # lxml has to be installed to process tables, this is just to check if it is installed


class DatalabData:
    """Class to retrieve and handle data from Datalab

    Parameters:
        api_key (str): the api key for the Datalab API
        domain (str): the domain of the Datalab instance
        collection_id (str): the collection id of the data to be retrieved
        blocktype (str): the blocktype of the data to be retrieved
        features (list): the features of the data to create csv table for BO

    Example usage:
    >>> retrieve_data = DatalabData(api_key, domain, collection_id, blocktype, features)
    >>> data_dataframe = retrieve_data.get_data()
    """

    def __init__(self, api_key, domain, collection_id, blocktype, features):
        self.api_key = api_key
        self.domain = domain
        self.collection_id = collection_id
        self.blocktype = blocktype
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
