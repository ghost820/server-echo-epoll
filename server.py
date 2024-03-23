from sys import exit
import logging
import socket
from select import epoll, EPOLLIN, EPOLLOUT, EPOLLHUP, EPOLLERR
from struct import unpack

SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 5000

clients = {}

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s]: %(message)s')

def add_client(client):
    clients[client.fileno()] = {
        'state': 'idle',
        'to_send': 0,
        'to_recv': 0,
        'handle': client,
        'data': b''
    }

def recv_packet_len(s):
    packet_len = s.recv(4)
    if len(packet_len) != 4:
        raise ConnectionError('The connection was terminated before data transfer was completed.')
    return unpack('>I', packet_len)[0]

def close_socket(s):
    try:
        del clients[s.fileno()]
    except:
        pass

    try:
        epoll_.unregister(s.fileno())
    except:
        pass

    try:
        s.shutdown(socket.SHUT_RDWR)
    except:
        pass

    try:
        s.close()
    except:
        pass

try:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((SERVER_ADDRESS, SERVER_PORT))
    server.listen()

    epoll_ = epoll()
    epoll_.register(server.fileno(), EPOLLIN)
except Exception as e:
    logging.error(f'Failed to run server: {e}')
    exit(1)

logging.info(f'Server is running on {SERVER_ADDRESS}:{SERVER_PORT}.')

try:
    end = False
    while not end:
        for fileno, event in epoll_.poll():
            if fileno == server.fileno():
                if event & EPOLLHUP:
                    raise Exception('EPOLLHUP event occurred on server socket.')
                elif event & EPOLLERR:
                    raise Exception('EPOLLERR event occurred on server socket.')
                elif event & EPOLLIN:
                    try:
                        client, address = server.accept()
                        client.setblocking(False)
                        epoll_.register(client.fileno(), EPOLLIN | EPOLLOUT)
                        add_client(client)
                        logging.info(f'Accept connection from {address}.')
                    except Exception as e:
                        logging.warning(f'Failed to accept connection: {e}')
                else:
                    logging.warning('Unknown event occurred on server socket.')
            else:
                client = clients[fileno]
                client_handle = client['handle']

                if event & (EPOLLHUP | EPOLLERR):
                    logging.warning(f'Connection was terminated with HUP|ERR event.')
                    close_socket(client_handle)
                elif event & EPOLLIN:
                    if client['state'] == 'idle':
                        try:
                            packet_len = recv_packet_len(client_handle)
                        except Exception as e:
                            logging.warning(f'Failed to receive packet length from {client_handle.getpeername()}: {e}')
                            close_socket(client_handle)
                            continue

                        client['state'] = 'recv'
                        client['to_recv'] = packet_len
                        client['data'] = b''
                    # Wait to the next iteration, packet needs more time to come after first send() with size.
                    elif client['state'] == 'recv':
                        try:
                            data = client_handle.recv(client['to_recv'])
                            if len(data) == 0:
                                raise ConnectionError('The connection was terminated before data transfer was completed.')
                        except Exception as e:
                            logging.warning(f'Failed to receive data from {client_handle.getpeername()}: {e}')
                            close_socket(client_handle)
                            continue

                        client['data'] += data
                        client['to_recv'] -= len(data)

                        if client['to_recv'] == 0:
                            client['state'] = 'send'
                            client['to_send'] = len(client['data'])
                elif event & EPOLLOUT:
                    if client['state'] == 'send':
                        try:
                            bytes_sent = client_handle.send(client['data'])
                        except Exception as e:
                            logging.warning(f'Failed to send data to {client_handle.getpeername()}: {e}')
                            close_socket(client_handle)
                            continue

                        client['data'] = client['data'][bytes_sent:]
                        client['to_send'] -= bytes_sent

                        if client['to_send'] == 0:
                            client['state'] = 'idle'
                else:
                    logging.warning(f'Unknown event occurred for {client_handle.getpeername()}.')
except KeyboardInterrupt:
    pass
except Exception as e:
    logging.error('Critical error occurred during server execution. Exiting...')
    logging.error(e)
    exit(2)

for fileno in list(clients.keys()):
    close_socket(clients[fileno]['handle'])
close_socket(server)
epoll_.close()
