#!/usr/bin/env python
# -*- coding: utf-8 -*-
# MIT License
#
# Copyright (c) 2017 Colter McQuay
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
import Queue
import numpy
from gnuradio import gr
from threading import Lock
from flex import FlexApi
from RingBuffer import RingBuffer


class FlexSource(gr.sync_block):
    """
    The FlexSource block used for streaming and interacting with IQ Data Streams
    from the Flex Radio.
    """
    def __init__(self):
        gr.sync_block.__init__(self,
                               name="source",
                               in_sig=None,
                               out_sig=[numpy.float32])
        self.rx_buffer = None
        self.radio = None
        self.iq_stream = None
        self.pan_adapter = None

    # TODO: Figure out how to do the following without leaking memory
    def __iq_data_received(self, iq_stream, data):
        try:
            # See the work method for explanation of what's going on
            # [self.received_queue.put(float(num)) for num in data] 
            
            self.rx_buffer.add([float(num) for num in data])
        except RingBuffer.Full:
            # queue is full, drop packets I guess
            print("Buffer Fulle:Packet Dropped")
            pass
        except Exception as err:
            print(err) 


    """
    Start method of GNU Block:
        - Get's active radio from api
        - Get's / creates Panadapter
        - Creates IQ Stream and begins listening
    """
    def start(self):
        self.rx_buffer = RingBuffer(4096) # 4 times the UDP payload size
        print "FlexSource::Starting..."
        self.radio = FlexApi().getRadio()
        
        # TODO: make these parameters of source block
        dax_ch = 1
        center_freq = 14.070
        sample_rate = 192000
        
        print "FlexSource::GetOrCreatePanAdapter"
        pans = self.radio.WaitForPanadaptersSync()
        # Close any panAdapters currently setup
        # TODO: Probably not necessary to clean them all up as it will destroy other client's panadapters
        for p in pans:
            p.Close(True)
        self.pan_adapter = self.radio.GetOrCreatePanadapterSync(0, 0)
        self.pan_adapter.DAXIQChannel = dax_ch
        self.pan_adapter.CenterFreq = center_freq

        print "FlexSource::CreatingIQStream"
        self.iq_stream = self.radio.CreateIQStreamSync(dax_ch)
        self.iq_stream.DataReady += self.__iq_data_received
        self.iq_stream.SampleRate = sample_rate
        print "FlexSource::IQStreamCreated"
        return True

    """
    Cleans up the Flex resources being used by this block
    """
    def stop(self):
        print("FlexSource::Removing IQ & Pan Adapter")
        self.iq_stream.DataReady -= self.__iq_data_received
        self.pan_adapter.Close(True)                
        self.iq_stream.Close()
        del self.rx_buffer
        #self.received_queue.join()
        print("FlexSource::Removed IQ & Panadapter, finished Queue")
        return True

    """
    Since the Flex radio is pushing data to this computer via UDP,
    we push the data onto a queue and inside the work method (GNU-Radio's api)
    we pull the appropriate amount of data off of the queue and push it into the
    output buffer of the gnu block
    """
    def work(self, input_items, output_items):
        out = output_items[0]
        num_outputs = 0
        try:
            items = self.rx_buffer.get(out.size)
            num_outputs = items.size
            out[0:num_outputs] = items
        except RingBuffer.Empty:
            # Don't care, just an empty buffer
            pass
        
        return num_outputs


        #     for i in range(0, out.size - 1):
        #         num = self.received_queue.get_nowait()
        #         #out[i] = self.received_queue.get_nowait()                
        #         #self.received_queue.task_done()
        #         #num_outputs = i
        # except Queue.Empty:
        #     # Happens when the queue is empty, no prob
        #     pass
        # return num_outputs
