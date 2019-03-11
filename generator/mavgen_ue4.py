#!/usr/bin/env python
'''
parse a MAVLink protocol XML file and generate a C implementation

Copyright Andrew Tridgell 2011
Released under GNU GPL version 3 or later
'''
from __future__ import print_function
from future.utils import iteritems
from functools import reduce

import os
from . import mavparse, mavtemplate

t = mavtemplate.MAVTemplate()

ue4_plugin_name = 'MavLinkMsgs'
ue4_plugin_name_upper = ue4_plugin_name.upper()

map = {
        'float'    : 'float',
        'double'   : 'double',
        'char'     : 'uint8',
        'int8_t'   : 'int8',
        'uint8_t'  : 'uint8',
        'uint8_t_mavlink_version'  : 'uint8',
        'int16_t'  : 'int16',
        'uint16_t' : 'uint16',
        'int32_t'  : 'int32',
        'uint32_t' : 'uint32',
        'int64_t'  : 'int64',
        'uint64_t' : 'uint64',
        }

def generate_dispatch_h(directory, xml):
    '''generate main header per XML file'''
    f = open(os.path.join(directory, xml.basename + "_dispatch.h"), mode='w')
    t.write(f, '''#pragma once

#include "CoreMinimal.h"
#include "${basename}_dispatch.generated.h"

USTRUCT(BlueprintType)
struct F${basename}Dispatch
{
    GENERATED_BODY()
};
''', xml)

    f.close()
             

def generate_message_h(path, m):
    '''generate per-message header for a XML file'''
    f = open(os.path.join(path, 'MavLinkMsg_%s.h' % m.name_lower), mode='w')
    
    t.write(f, ''' 
#pragma once

#include "CoreMinimal.h"
#include "MavLinkMsg_${name_lower}.generated.h"

struct __mavlink_message;

USTRUCT(BlueprintType)
struct MAVLINKMSGS_API FMavlinkMsg_${name_lower}
{
    GENERATED_BODY()

    ${{fields:/*${description} ${units}*/
    UPROPERTY()
    ${type} ${name}${array_suffix};

    }}

    void Serialize(uint8 systemId, uint8 componentId, __mavlink_message& msg, uint16& packSize);
    void Serialize(uint8 systemId, uint8 componentId, TSharedRef<TArray<uint8>, ESPMode::ThreadSafe>& buffer);
    void Deserialize(const __mavlink_message& msg);
    
};
''', m)
    f.close()

def generate_message_cpp(path, m):
    '''generate per-message header for a XML file'''
    f = open(os.path.join(path, 'MavLinkMsg_%s.cpp' % m.name_lower), mode='w')
    
    t.write(f, ''' 
#include "MavLinkMsg_${name_lower}.h"
#include "${dialect_name}/mavlink.h"

void FMavlinkMsg_${name_lower}::Serialize(uint8 systemId, uint8 componentId, __mavlink_message& msg, uint16& packSize)
{
    packSize = mavlink_msg_${name_lower}_pack(systemId, componentId, &msg, ${{arg_fields: ${array_arg_cast}${name},}});
}

void FMavlinkMsg_${name_lower}::Serialize(uint8 systemId, uint8 componentId, TSharedRef<TArray<uint8>, ESPMode::ThreadSafe>& buffer)
{
    uint16 size;
    __mavlink_message msg;
    Serialize(systemId, componentId, msg, size);
    buffer->SetNum(size);
    mavlink_msg_to_send_buffer(buffer->GetData(), &msg);
}

void FMavlinkMsg_${name_lower}::Deserialize(const mavlink_message_t& msg)
{

}

''', m)
    f.close()

def copy_plugin_content(directory, xml):
    
    basepath = os.path.dirname(os.path.realpath(__file__))
    files = ['MavLinkMsgs.uplugin' ,'Source/ThirdParty/mavlink_c/mavlink_c.Build.cs', 'Source/MavLinkMsgs/MavLinkMsgs.Build.cs', 
    'Source/MavLinkMsgs/Private/MavLinkMsgs.cpp', 'Source/MavLinkMsgs/Public/MavLinkMsgs.h']
    src_path = os.path.join(basepath, 'UE4')
    import shutil
    
    for file in files:
        src_file_path = os.path.realpath(reduce(os.path.join, [src_path, "Plugin", file]))
        dst_file_path = os.path.realpath(os.path.join(directory, file))
        if not os.path.exists(os.path.dirname(dst_file_path)):
            mavparse.mkdir_p(os.path.dirname(dst_file_path))
        shutil.copy(src_file_path, dst_file_path)

def generate_one(plugin_path, xml):

    mavlinkmsgs_public_path = os.path.realpath(os.path.join(plugin_path, 'public/%s' % xml.basename))
    mavlinkmsgs_private_path = os.path.realpath(os.path.join(plugin_path, 'private/%s' % xml.basename))

    mavparse.mkdir_p(mavlinkmsgs_public_path)
    mavparse.mkdir_p(mavlinkmsgs_private_path)

    #fixup types that UE doesn't like(remove _t)
    for m in xml.message: 
        m.dialect_name = xml.basename

        for f in m.fields:
            orig_type = f.type
            f.type = map[f.type]
            f.array_arg_cast = ''
            if f.array_length != 0 and orig_type != f.type:
                f.array_arg_cast = '(%s*)' % (orig_type)

                #f.array_suffix = ".GetData()"
                #f.type = "TArray<%s, TFixedAllocator<%s>>" % (f.type, f.array_length)
                


    for m in xml.message:
            generate_message_h(mavlinkmsgs_public_path, m)
            generate_message_cpp(mavlinkmsgs_private_path, m)

class mav_include(object):
    def __init__(self, base):
        self.base = base

def generate(basename, xml_list):
    '''generate serialization MAVLink UE4 implemenation'''
    print("Generating C headers")
    from . import mavgen_c
    ue4_plugin_base_path = os.path.join(basename, ue4_plugin_name)

    ue4_third_party_path = os.path.realpath(os.path.join(ue4_plugin_base_path, "Source/ThirdParty"))
    mavlinkmsgs_base_path = os.path.realpath(os.path.join(ue4_plugin_base_path, 'Source/MavLinkMsgs'))

    copy_plugin_content(ue4_plugin_base_path, xml_list)
    mavgen_c.generate(os.path.join(ue4_third_party_path, 'mavlink_c/include/'), xml_list)
    

    for idx in range(len(xml_list)):
        xml = xml_list[idx]
        xml.xml_idx = idx
        generate_one(mavlinkmsgs_base_path, xml)
        
       
