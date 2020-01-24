"""Module to manipulate objects in Blender regarding CityJSON"""

import json
import time

import bpy
import idprop

from .material import (BasicMaterialFactory, ReuseMaterialFactory,
                       CityObjectTypeMaterialFactory)
from .utils import (assign_properties, clean_buffer, clean_list,
                    coord_translate_axis_origin, remove_scene_objects,store_semantics)


def cityJSON_exporter(context, filepath):
    start=time.time()

    print("\nExporting CityJSON file...")
    
    minimal_json = {
        "type": "CityJSON",
        "version": "1.0",
        "extensions": {},
        "metadata": {},
        "CityObjects": {},
        "vertices":[]
    }
    progress_max = len(bpy.data.objects)
    progress = 0

    cityjson_vertices_index = 0
    #Create a list of vertices to store the global vertices of all objects
    vertices = list()
    for city_object in bpy.data.objects:
        
        #Empty objects have all the attributes
        if city_object.type=='EMPTY':
            name=city_object.name
            minimal_json["CityObjects"].setdefault(name,{})
            minimal_json["CityObjects"][name].setdefault('geometry',[])

           
            #Get all the custom properties of the object
            cp=city_object.items()
            for prop in cp:
                split = prop[0].split(".")
                
                #Check if the attribute is IDPropertyArray. JSON encoder cannot handle this type
                if isinstance(prop[1],idprop.types.IDPropertyArray):
                    #convert type IDPropertyArray to python list
                    attribute=prop[1].to_list()
                else:
                    attribute=prop[1]
                #Split is the spliited name of the atributes where "." | Every "." represents one level below in the dictionart              
                if len(split)==3:
                    if not (split[0] in  minimal_json["CityObjects"][name]):
                        minimal_json["CityObjects"][name].update({split[0]:{}})
                   
                    if not (split[1] in  minimal_json["CityObjects"][name][split[0]]):    
                        minimal_json["CityObjects"][name][split[0]].update({split[1]:{}})
                       
                    if not (split[2] in  minimal_json["CityObjects"][name][split[0]][split[1]]):   
                        minimal_json["CityObjects"][name][split[0]][split[1]].update({split[2]:attribute})
                elif len(split)==2:
                   
                    if not (split[0] in  minimal_json["CityObjects"][name]):
                        minimal_json["CityObjects"][name].update({split[0]:{}})
                       
                    if not (split[1] in  minimal_json["CityObjects"][name][split[0]]):
                        minimal_json["CityObjects"][name][split[0]].update({split[1]:attribute})
                else:
                    if not (split[0] in  minimal_json["CityObjects"][name]):
                        minimal_json["CityObjects"][name].update({split[0]:attribute})

        
        #If the object is MESH means that is an actual geometry contained in the CityJSON file
        if city_object.type =='MESH':
            
            name = city_object.name
            #Trim the name to remove the extra prefix added upon importing
            original_objects_name = name[10:]
            minimal_json["CityObjects"].setdefault(original_objects_name,{})
            minimal_json["CityObjects"][original_objects_name].setdefault('geometry',[])

            #Check if object has materials (in Blender) i.e semantics in real life and if yes create the extra tags to store it
            if city_object.data.materials:
                minimal_json["CityObjects"][original_objects_name]['geometry'].append({'type':city_object['type'],'boundaries':[],'semantics':{},'texture':{},'lod':city_object['lod']})
            else:
                minimal_json["CityObjects"][original_objects_name]['geometry'].append({'type':city_object['type'],'boundaries':[],'lod':city_object['lod']}) 
                        
            #Accessing specific object's vertices coordinates 
            specific_object_verts = city_object.data.vertices
            #Accessing specific object's faces
            specific_object_faces = city_object.data.polygons

            #Browsing through faces and their vertices of every object. | Since the structure that the geometry is stored is different with respect to the geometry type 
            #the geometry type is checked for every object. Case of multisolid hasn't been taken under consideration. 
            #In case the object has semantics they are accordingly stored as well
            if city_object['type'] == 'MultiSurface':
                   
                for face in specific_object_faces:
                    minimal_json["CityObjects"][original_objects_name]["geometry"][city_object['lod']]["boundaries"].append([[]])
                   
                    for i in range(len(specific_object_faces[face.index].vertices)):
                        
                        original_index = specific_object_faces[face.index].vertices[i]
                        get_vertex = specific_object_verts[original_index]
                        if get_vertex.co in vertices:    
                            vert_index = vertices.index(get_vertex.co)
                            minimal_json["CityObjects"][original_objects_name]["geometry"][city_object['lod']]["boundaries"][face.index][0].append(vert_index)
                        else:
                            vertices.append(get_vertex.co)
                            minimal_json["CityObjects"][original_objects_name]["geometry"][city_object['lod']]["boundaries"][face.index][0].append(cityjson_vertices_index)
                            cityjson_vertices_index += 1
                    
                    store_semantics(minimal_json,city_object,original_objects_name,face)

            if city_object['type'] == 'Solid':
                
                minimal_json["CityObjects"][original_objects_name]["geometry"][city_object['lod']]["boundaries"].append([])
                for face in specific_object_faces:
                    minimal_json["CityObjects"][original_objects_name]["geometry"][city_object['lod']]["boundaries"][0].append([[]])
                                        
                    for i in range(len(specific_object_faces[face.index].vertices)):
                        original_index = specific_object_faces[face.index].vertices[i]
                        
                        get_vertex = specific_object_verts[original_index]
                        if get_vertex.co in vertices:
                            vert_index = vertices.index(get_vertex.co)
                            minimal_json["CityObjects"][original_objects_name]["geometry"][city_object['lod']]["boundaries"][0][face.index][0].append(vert_index)
                        else:
                            vertices.append(get_vertex.co)
                            minimal_json["CityObjects"][original_objects_name]["geometry"][city_object['lod']]["boundaries"][0][face.index][0].append(cityjson_vertices_index)
                            cityjson_vertices_index += 1
                                       
                    store_semantics(minimal_json,city_object,original_objects_name,face)
                  
        progress += 1
        print("Exporting: {percent}% completed".format(percent=round(progress * 100 / progress_max, 1)),end="\r")
    
    
    #Writing vertices to minimal_json
    for vert in vertices:
        coord = city_object.matrix_world @ vert
        minimal_json['vertices'].append([coord[0],coord[1],coord[2]])
       
    print ("\nWriting to CityJSON file...")
    #Writing CityJSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(minimal_json, f, ensure_ascii=False, indent=4)
    
    end=time.time()

    print("\n")
    print("CityJSON file successfully exported!\n")
    print("Total Exporting Time: ", round(end-start, 2), "s")
    
    
    return{'FINISHED'}       
            
"""TODO Fix the indexing of vertices when more than one objects are added. At the moment it works correctly only with 
one object. The other is distorted due to bad indexing of appropriate vertices """

def get_geometry_name(objid, geom, index):
    """Returns the name of the provided geometry"""
    if 'lod' in geom:
        return "{index}: [LoD{lod}] {name}".format(name=objid, lod=geom['lod'], index=index)
    else:
        return "{index}: [GeometryInstance] {name}".format(name=objid, index=index)

def create_empty_object(name):
    """Returns an empty blender object"""

    new_object = bpy.data.objects.new(name, None)

    return new_object

def create_mesh_object(name, vertices, faces, materials=[], material_indices=[]):
    """Returns a mesh blender object"""

    mesh_data = None

    if faces:
        mesh_data = bpy.data.meshes.new(name)

        for material in materials:
            mesh_data.materials.append(material)

        indices = [i for face in faces for i in face]

        mesh_data.vertices.add(len(vertices))
        mesh_data.loops.add(len(indices))
        mesh_data.polygons.add(len(faces))

        coords = [c for v in vertices for c in v]

        loop_totals = [len(face) for face in faces]
        loop_starts = []
        i = 0
        for face in faces:
            loop_starts.append(i)
            i += len(face)

        mesh_data.vertices.foreach_set("co", coords)
        mesh_data.loops.foreach_set("vertex_index", indices)
        mesh_data.polygons.foreach_set("loop_start", loop_starts)
        mesh_data.polygons.foreach_set("loop_total", loop_totals)
        if len(material_indices) == len(faces):
            mesh_data.polygons.foreach_set("material_index", material_indices)
        elif len(material_indices) > len(faces):
            print("Object {name} has {num_faces} faces but {num_surfaces} semantic surfaces!"
                  .format(name=name,
                          num_faces=len(faces),
                          num_surfaces=len(material_indices)))

        mesh_data.update()

    new_object = bpy.data.objects.new(name, mesh_data)

    return new_object

def get_collection(collection_name):
    """Returns a collection with the given name"""

    if collection_name in bpy.data.collections:
        return bpy.data.collections[collection_name]
    
    new_collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(new_collection)

    return new_collection

class CityJSONParser:
    """Class that parses a CityJSON file to Blender"""

    def __init__(self, filepath, material_type, reuse_materials=True, clear_scene=True):
        self.filepath = filepath
        self.clear_scene = clear_scene

        self.data = {}
        self.vertices = []

        if material_type == 'SURFACES':
            if reuse_materials:
                self.material_factory = ReuseMaterialFactory()
            else:
                self.material_factory = BasicMaterialFactory()
        else:
            self.material_factory = CityObjectTypeMaterialFactory()

    def load_data(self):
        """Loads the CityJSON data from the file"""

        with open(self.filepath) as json_file:
            self.data = json.load(json_file)

    def prepare_vertices(self):
        """Prepares the vertices by applying any required transformations"""

        vertices = []

        # Checking if coordinates need to be transformed and
        # transforming if necessary
        if 'transform' not in self.data:
            for vertex in self.data['vertices']:
                vertices.append(tuple(vertex))
        else:
            trans_param = self.data['transform']
            # Transforming coords to actual real world coords
            for vertex in self.data['vertices']:
                x = vertex[0]*trans_param['scale'][0] \
                    + trans_param['translate'][0]
                y = vertex[1]*trans_param['scale'][1] \
                    + trans_param['translate'][1]
                z = vertex[2]*trans_param['scale'][2] \
                    + trans_param['translate'][2]

                vertices.append((x, y, z))

        # Translating coordinates to the axis origin
        translation = coord_translate_axis_origin(vertices)

        # Updating vertices with new translated vertices
        self.vertices = translation[0]

    def parse_geometry(self, theid, obj, geom, index):
        """Returns a mesh object for the provided geometry"""
        bound = []

        # Checking how nested the geometry is i.e what kind of 3D
        # geometry it contains
        if (geom['type'] == 'MultiSurface'
                or geom['type'] == 'CompositeSurface'):
            for face in geom['boundaries']:
                if face:
                    bound.append(tuple(face[0]))
        elif geom['type'] == 'Solid':
            for shell in geom['boundaries']:
                for face in shell:
                    if face:
                        bound.append(tuple(face[0]))
        elif geom['type'] == 'MultiSolid':
            for solid in geom['boundaries']:
                for shell in solid:
                    for face in shell:
                        if face:
                            bound.append(tuple(face[0]))

        temp_vertices, temp_bound = clean_buffer(self.vertices, bound)

        mats, values = self.material_factory.get_materials(cityobject=obj,
                                                           geometry=geom)

        geom_obj = create_mesh_object(get_geometry_name(theid, geom, index),
                                      temp_vertices,
                                      temp_bound,
                                      mats,
                                      values)

        if 'lod' in geom:
            geom_obj['lod'] = geom['lod']

        geom_obj['type'] = geom['type']

        return geom_obj

    def execute(self):
        """Execute the import process"""

        if self.clear_scene:
            remove_scene_objects()

        print("\nImporting CityJSON file...")

        self.load_data()

        self.prepare_vertices()

        new_objects = []
        cityobjs = {}

        progress_max = len(self.data['CityObjects'])
        progress = 0
        start_import = time.time()

        # Creating empty meshes for every CityObjects and linking its
        # geometries as children-meshes
        for objid, obj in self.data['CityObjects'].items():
            cityobject = create_empty_object(objid)
            cityobject = assign_properties(cityobject,
                                           obj)
            new_objects.append(cityobject)
            cityobjs[objid] = cityobject

            for i, geom in enumerate(obj['geometry']):
                geom_obj = self.parse_geometry(objid, obj, geom, i)
                geom_obj.parent = cityobject
                new_objects.append(geom_obj)

            progress += 1
            print("Importing: {percent}% completed"
                  .format(percent=round(progress * 100 / progress_max, 1)),
                  end="\r")
        end_import = time.time()

        progress = 0
        start_hier = time.time()

        #Assigning child building parts to parent buildings
        for objid, obj in self.data['CityObjects'].items():
            if 'parents' in obj:
                parent_id = obj['parents'][0]
                cityobjs[objid].parent = cityobjs[parent_id]

            progress += 1
            print("Building hierarchy: {percent}% completed"
                  .format(percent=round(progress * 100 / progress_max, 1)),
                  end="\r")
        end_hier = time.time()

        start_link = time.time()

        # Link everything to the scene
        collection = bpy.context.scene.collection
        for new_object in new_objects:
            if 'lod' in new_object:
                get_collection("LoD{}".format(new_object['lod'])).objects.link(new_object)
            else:
                collection.objects.link(new_object)


        end_link = time.time()

        #Console output
        print("\n")
        print("CityJSON file successfully imported!\n")
        print("Total Importing Time: ", round(end_import-start_import, 2), "s")
        print("Building Hierarchy: ", round(end_hier-start_hier, 2), "s")
        print("Linking: ", round(end_link-start_link, 2), "s")

        return {'FINISHED'}
