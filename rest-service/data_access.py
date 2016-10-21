import os
import time
import sqlite3
import kgeserver.server as server
import kgeserver.dataset as dataset
import kgeserver.wikidata_dataset as wikidata_dataset
database_file = "server.db"


class MainDAO():
    def __init__(self, database_file="server.db"):
        "Comprueba si existe la base de datos y/o la inicializa"

        self.database_file = database_file

        # Create the file itself
        try:
            os.stat(self.database_file)
        except OSError:
            # File does not exist. Create
            f = open(self.database_file, "w+")
            f.close()
            self.build_basic_db()

        # Path where all binary files have its relative path
        self.bin_path = "../"

    def build_basic_db(self):
        self.execute_query("CREATE TABLE dataset "
                           "(id INTEGER UNIQUE PRIMARY KEY, "
                           "binary_dataset TEXT, "
                           "binary_model TEXT, "
                           "binary_index TEXT,"
                           "embedding_size INTEGER, status INTEGER)")

        self.execute_query("INSERT INTO dataset VALUES "
                           "(0, 'wikidata_25k.bin', '', "
                           "'wikidata_25k.annoy.bin', 100, 2)")

        self.execute_query("INSERT INTO dataset VALUES "
                           "(1, '4levels.bin', 'modelo_guardado.bin', "
                           "'annoy_index_big.bin', 100, 2)")
        self.execute_query("INSERT INTO dataset VALUES "
                           "(2, '4levels.bin', 'modelo_guardado.bin', "
                           "'annoyIndex.500.bin', 100, 2)")

    def execute_query(self, query):
        conn = sqlite3.connect(self.database_file)
        c = conn.cursor()
        c.execute(query)
        row = c.fetchone()
        conn.commit()
        c.close()
        return row

    def execute_insertion(self, query):
        conn = sqlite3.connect(self.database_file)
        c = conn.cursor()
        c.execute(query)
        conn.commit()
        return c


class DatasetDAO(MainDAO):
    """Object to interact between the data storage and returns valid objects

    All methods that shows a "return tuple", it returns a pair, where first
    element is an object if no error found or None if error are found. Details
    of the error can be queried on the other element of the pair.

    Example without error: (dataset.Dataset, None)
    Example with error: (None, (404, "Not found on database"))
    """

    def __init__(self, database_file="server.db"):
        """Instantiates the object and creates *private* variables
        """
        super(DatasetDAO, self).__init__(database_file=database_file)
        self.dataset = {
            "status": None,
            "entities": None,
            "relations": None,
            "triples": None,
            "algorithm": None,
            "id": None
        }
        self.binary_dataset = None
        self.binary_model = None
        self.binary_index = None
        self.embedding_size = None

    def get_dataset_by_id(self, dataset_id):
        """Returns a dataset given its id

        :return: A dataset dictionary or none
        :rtype: tuple
        """
        query = "SELECT * FROM dataset WHERE id={0}".format(dataset_id)
        res = self.execute_query(query)
        # Query has return nothing
        if res is None:
            return None, (404, "Dataset {} not found".format(dataset_id))
        # Query has an object
        self.binary_dataset = res[1]
        self.binary_model = res[2]
        self.binary_index = res[3]
        self.embedding_size = res[4]
        dtst = dataset.Dataset()
        dtst.load_from_binary(self.bin_path+self.binary_dataset)
        self.dataset['status'] = res[5]
        self.dataset['algorithm'] = res[4]
        self.dataset['triples'] = len(dtst.subs)
        self.dataset['entities'] = len(dtst.entities)
        self.dataset['relations'] = len(dtst.relations)
        self.dataset['id'] = int(dataset_id)
        return (self.dataset, dtst)

    def get_search_index(self):
        """Returns an instantiated search index from choosen dataset

        """
        if self.dataset['status'] < 2:
            return None, (409, "Dataset {id} has {status} status and is not "
                               "ready for search".format(**self.dataset))
        search_index = server.SearchIndex()
        search_index.load_from_file(self.bin_path + self.binary_index,
                                    self.embedding_size)
        return search_index, None

    def get_server(self):
        """Returns the server with the correct search index loaded.

        :return: The Server object or None
        :rtype: tuple
        """
        search_index, err = self.get_search_index()
        if search_index is None:
            return None, err
        else:
            return server.Server(search_index), None

    def insert_empty_dataset(self, datasetClass):
        """Creates an empty dataset on database.

        :param kgeserver.dataset.Dataset datasetClass: The class of the dataset
        :return: The id of dataset created, or None
        :rtype: tuple
        """
        unique_name = str(int(time.time()))+".bin"
        sql_sentence = ("INSERT INTO dataset VALUES "
                        "(NULL, '"+unique_name+"', '', '', 0, 0)")

        newdataset = datasetClass()
        newdataset.save_to_binary(self.bin_path+unique_name)

        result = self.execute_insertion(sql_sentence)
        rowid = result.lastrowid
        result.close()
        return rowid, None

    def get_all_datasets(self):
        """Queries the DB to retrieve all datasets

        :returns: A list of datasets objects
        :rtype: list
        """

    def get_dataset_types(self):
        """Stores the different datasets that can be created

        :returns: A list of objects
        :rtype: list
        """
        return [
            {
                "id": 0,
                "name": "dataset",
                "class": dataset.Dataset
            },
            {
                "id": 1,
                "name": "WikidataDataset",
                "class": wikidata_dataset.WikidataDataset
            }
        ]
