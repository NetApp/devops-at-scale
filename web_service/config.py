import os


class BaseConfig:
    """Base configuration"""
    DEBUG = False
    TESTING = False
    DATABASE_URL=os.getenv('DATABASE_URL','build-at-scale-couchdb.default:5984')
    DATABASE_USER = os.getenv('DATABASE_USER','admin')
    DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD','admin')
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'build_at_scale')
    BUILD_AT_SCALE_VERSION = os.getenv('BUILD_AT_SCALE_VERSION', 'latest')
    # The below ontap variables are only used once when configuring build@scale for the first time
    # Therafter , this information is retrieved from couchdb
    ONTAP_API = os.getenv('ONTAP_API','')
    ONTAP_APIUSER = os.getenv('ONTAP_APIUSER','')
    ONTAP_APIPASS = os.getenv('ONTAP_APIPASS','')
    ONTAP_SVM_NAME = os.getenv('ONTAP_SVM_NAME','')
    ONTAP_AGGR_NAME = os.getenv('ONTAP_AGGR_NAME','')
    ONTAP_DATA_IP = os.getenv('ONTAP_DATA_IP','')
    SCM_TYPE = os.getenv('SCM_TYPE','')
    REGISTRY_TYPE = os.getenv('REGISTRY_TYPE','')
    SERVICE_TYPE = os.getenv('SERVICE_TYPE','')

class TestingConfig(BaseConfig):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    DATABASE_NAME = 'test_build_at_scale'

class ProductionConfig(BaseConfig):
    """Production configuration"""
    DEBUG = False
