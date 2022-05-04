MoleGuLAR-Web
===================

This repository contains a web app implementation of [MoleGuLAR](https://github.com/devalab/MoleGuLAR).

<!-- ![image](https://github.com/devalab/MoleGuLAR/blob/master/Images/MainDiagram.png) -->
<img src="https://raw.githubusercontent.com/devalab/MoleGuLAR/master/Images/MainDiagram.png">

It contains three microservices - the server, trainer and evaluator implemented in FastAPI. All the requests from the client go to the server which then accordingly sends a request to the trainer or evaluator.

## Setup

To setup the app locally for development

```shell
git clone https://github.com/manangoel99/MoleGuLAR-Web
git submodule update --init --recursive
```

This will clone the repository locally and fetch the AutoDock-GPU package required for docking calculations. For running the app, you will need to setup docker and docker-compose. The documentation for those are available [here](https://docs.docker.com/engine/install/) and [here](https://docs.docker.com/compose/install/) respectively. To build and run the app, use the following command

```shell
docker-compose up --build
```

This will build each microservice in seperate docker containers and link them all on a common network for interacting with each other. The database of choice is PostgreSQL again pulled from a docker image so does not require any local setup.

## Architecture
<img src="https://s3.us-west-2.amazonaws.com/secure.notion-static.com/026c910f-a11a-4d27-93f7-6d6e5c6a6479/Untitled.png?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=AKIAT73L2G45EIPT3X45%2F20220504%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20220504T065419Z&X-Amz-Expires=86400&X-Amz-Signature=e27f8d76003747f91b17783e217455e9e8cb40548882ac028a27cd883296b193&X-Amz-SignedHeaders=host&response-content-disposition=filename%20%3D%22Untitled.png%22&x-id=GetObject">

The client will send requests to the server. If the user requests a training job or status of all jobs, the request is sent to the trainer. The trainer processes the training jobs asynchronously using ray. All training jobs use only 1 GPU and if the machine possesses more than 1 GPU, the submitted jobs are distributed accordingly. The trained models are saved after every iteration during training.

If the user requests an evaluation job, the evaluator service will receive a request from the server to generate the number of molecules requested by the user. This is a blocking operation and the response will be a list of generated SMILES and their corresponding properties.