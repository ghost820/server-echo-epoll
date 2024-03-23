#include <iostream>
#include <array>
#include <string>
#include <string_view>
#include <exception>
#include <random>
#include <thread>
#include <cstdint>
#include <cstdlib>

#include <arpa/inet.h>

#include "Socket.h"

constexpr const char* const ADDRESS = "127.0.0.1";
constexpr unsigned int PORT = 5000;

constexpr unsigned int NUM_OF_THREADS = 10;
constexpr unsigned int NUM_OF_MSGS_PER_CONN = 1000;
constexpr unsigned int PAYLOAD_MAX_SIZE = 1048576;

std::mt19937 randomEngine;
std::uniform_int_distribution<unsigned int> rndPacketSize(1, PAYLOAD_MAX_SIZE);

std::array<std::string, NUM_OF_MSGS_PER_CONN> payloads;

void expectResponse(GSock::Socket& s, std::string_view msg, std::string_view expectedResponse) {
    try {
        uint32_t msgSize = htonl(msg.size());
        s.send(std::string_view(reinterpret_cast<char*>(&msgSize), sizeof(msgSize)));
        s.send(msg);

        std::string res = s.recvAll(msg.size());

        if (res != msg) {
            std::cerr << "Received message does not match sent message.\n";
            exit(1);
        }

        std::cout << "Test for message of size " << msg.size() << " passed.\n";
    }
    catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        exit(1);
    }
}

void worker() {
    try {
        while (true) {
            GSock::Socket s(ADDRESS, PORT);

            for (unsigned int i = 0; i < NUM_OF_MSGS_PER_CONN; ++i) {
                expectResponse(s, payloads[i], payloads[i]);
            }
        }
    }
    catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        exit(1);
    }
}

int main() {
    for (int i = 0; i < NUM_OF_MSGS_PER_CONN; ++i) {
        payloads[i] = std::string(rndPacketSize(randomEngine), 'a');
    }

    for (unsigned int i = 0; i < NUM_OF_THREADS; ++i) {
        std::thread(worker).detach();
    }

    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}
