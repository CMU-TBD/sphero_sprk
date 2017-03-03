"""A setuptools based setup module.
Modified from https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages

setup (
    name='sphero_sprk',
    version='0.1.0',
    description="Python Module that commands Sphero SPRK+",
    url='https://github.com/CMU-ARM/sphero_sprk',
    author= "Xiang Zhi Tan",
    author_email = "zhi.tan@ri.cmu.edu",
    keywords = ['Sphero','SPRK'],
    classifiers = [
        'Development Status :: 3 - Alpha',
        #We only support python3
        'Programming Language :: Python :: 3.3'
    ],
    install_requires=[
       'bluepy',
       'pyyaml'
    ],
    #packages=find_packages(exclude=['docs', 'tests*','res']),
    packages=['sphero_sprk'],
    package_data={
        'sphero_sprk':['data/*.yaml']
    },
    #include_package_data=True
)