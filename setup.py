from pathlib import Path

from setuptools import find_packages, setup

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="girder-sample-tracker",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version="2.0.5",
    description="Girder Plugin adding a simple tracker for material samples",
    packages=find_packages(),
    include_package_data=True,
    license="BSD",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
    python_requires=">=3.10",
    setup_requires=["setuptools-git"],
    install_requires=["girder>=5.0.0a5.dev0", "qrcode[pil]", "cairosvg"],
    entry_points={"girder.plugin": ["sample_tracker = girder_sample_tracker:SampleTrackerPlugin"]},
    zip_safe=False,
)
