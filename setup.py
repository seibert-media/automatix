from setuptools import find_packages, setup

setup(
    name='automatix',
    version='0.0.3',
    description='Automation wrapper for bash and python commands',
    url='https://github.com/seibert-media/automatix',
    author='Johannes Paul, //SEIBERT/MEDIA GmbH',
    author_email='jpaul@seibert-media.net',
    license='MIT',
    python_requires='>=3.6',
    install_requires=[
        'pyyaml>=5.1',
    ],
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'automatix=automatix:main',
        ],
    },
)
