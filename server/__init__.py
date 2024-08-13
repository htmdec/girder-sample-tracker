from .rest.sample import Sample

def load(info):
    info["apiRoot"].sample = Sample()
