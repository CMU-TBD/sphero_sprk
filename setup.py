"""A setuptools based setup module.
Modified from https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages

setup (
    name='sphero_sprk',
    version='0.0.1',
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
    ],
    include_package_data=True
)