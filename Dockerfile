FROM public.ecr.aws/docker/library/python:3.9.13

ENV LOGGING_LEVEL="INFO"

COPY requirements.txt /
# Install build tools and curl
RUN apt-get update && \
    apt-get install -y build-essential curl && \
    rm -rf /var/lib/apt/lists/*
# Install Rust and Cargo using rustup
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
# Update PATH to include Cargo binaries
ENV PATH="/root/.cargo/bin:${PATH}"

RUN pip install wheel
RUN pip install --no-cache-dir -r /requirements.txt

WORKDIR /paradex
COPY . .
# Don't run as root: 65534 is 'nobody' in this image.
USER 65534:65534
# Replace `onboarding` with desired example script.
CMD ["python", "app.py"]
