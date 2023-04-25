# Ansible
* https://www.youtube.com/watch?v=lhFvMsy6VX8&list=PLy7NrYWoggjwwEpZO8sscD9X6EH39njz6&ab_channel=TechWorldwithNana


# Dockerfile
```
cat <<EOM > Dockerfile
FROM apache/airflow
USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         vim \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
USER airflow
EOM
```
