from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='automatix',
    version='1.11.1',
    description='Automation wrapper for bash and python commands',
    keywords=['bash', 'shell', 'command', 'automation', 'process', 'wrapper', 'devops', 'system administration'],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/seibert-media/automatix',
    author='Johannes Paul, //SEIBERT/MEDIA GmbH',
    author_email='jpaul@seibert-media.net',
    license='MIT',
    python_requires='>=3.6',
    install_requires=[
        'pyyaml>=5.1',
        'importlib-metadata >= 1.0 ; python_version < "3.8"',
    ],
    extras_require={
        'bash completion': 'argcomplete',
    },
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'automatix=automatix:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
