#!/bin/bash

#zmien wartosc przy parallel na liczbe rdzeni twojego procesora
git clone --depth=1 https://github.com/open-quantum-safe/liboqs
cmake -S liboqs -B liboqs/build -DBUILD_SHARED_LIBS=ON
cmake --build liboqs/build --parallel 8
sudo cmake --build liboqs/build --target install

export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib

#tutaj wpisz sciezke do zainstalowanej biblioteki liboqs
export OQS_INSTALL_PATH= #/path/to/liboqs

