FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:1
ENV COPPELIASIM_ROOT=/opt/CoppeliaSim
ENV LD_LIBRARY_PATH=/opt/CoppeliaSim
ENV QT_X11_NO_MITSHM=1
ENV LIBGL_ALWAYS_SOFTWARE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk \
    python3 \
    python3-pip \
    python3-requests \
    curl \
    wget \
    ca-certificates \
    xz-utils \
    procps \
    psmisc \
    xvfb \
    x11vnc \
    fluxbox \
    xterm \
    supervisor \
    novnc \
    websockify \
    libgl1 \
    libgl1-mesa-dri \
    libglu1-mesa \
    libglib2.0-0 \
    libxrender1 \
    libxext6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcb-xinerama0 \
    libxkbcommon-x11-0 \
    libdbus-1-3 \
    libfontconfig1 \
    libfreetype6 \
    libxi6 \
    libxrandr2 \
    libxinerama1 \
    libxcursor1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxss1 \
    libxtst6 \
    libasound2 \
    libpulse0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY vendor/CoppeliaSim_Edu_V4_3_0_Ubuntu20_04.tar.xz /tmp/coppelia.tar.xz
RUN mkdir -p /opt/CoppeliaSim \
    && tar -xJf /tmp/coppelia.tar.xz -C /opt/CoppeliaSim --strip-components=1 \
    && rm /tmp/coppelia.tar.xz \
    && chmod +x /opt/CoppeliaSim/coppeliaSim /opt/CoppeliaSim/coppeliaSim.sh \
    && test -x /opt/CoppeliaSim/coppeliaSim

COPY services/sim-vnc/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY services/sim-vnc/start.sh /start.sh
COPY services/sim-vnc/open-coppelia.sh /usr/local/bin/cogscore-open-coppelia
COPY services/sim-vnc/stop-coppelia.sh /usr/local/bin/cogscore-stop-coppelia

RUN chmod +x \
    /start.sh \
    /usr/local/bin/cogscore-open-coppelia \
    /usr/local/bin/cogscore-stop-coppelia

EXPOSE 5901 6080

CMD ["/start.sh"]
