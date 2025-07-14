from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='automatix',
    version='2.11.0',
    description='Automation wrapper for bash and python commands',
    keywords=['bash', 'shell', 'command', 'automation', 'process', 'wrapper', 'devops', 'system administration'],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/seibert-media/automatix',
    author='Johannes Paul',
    author_email='johannes.paul@seibert.group, vanadinit@quantentunnel.de',
    license='MIT',
    python_requires='>=3.10',
    install_requires=[
        'pyyaml>=5.1',
    ],
    extras_require={
        'tests': ['cython<3.0.0', 'pytest', 'pytest-docker', 'flake8'],
        'bash completion': ['argcomplete'],
    },
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'automatix=automatix:main',
            'automatix-manager=automatix.parallel:run_manager',
            'automatix-from-file=automatix.parallel:run_auto_from_file',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
