# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

#-------------------------- COLORS / GROUPS EXCHANGER -------------------------#
#                                                                              #
# Vertex Color to Vertex Group allow you to convert colors channles to weight  #
# maps.                                                                        #
# The main purpose is to use vertex colors to store information when importing #
# files from other softwares. The script works with the active vertex color    #
# slot.                                                                        #
# For use the command "Vertex Clors to Vertex Groups" use the search bar       #
# (space bar).                                                                 #
#                                                                              #
#                          (c)  Alessandro Zomparelli                          #
#                                     (2017)                                   #
#                                                                              #
# http://www.co-de-it.com/                                                     #
#                                                                              #
################################################################################

import bpy, bmesh, os
import numpy as np
import math, timeit, time
from math import pi
from statistics import mean, stdev
from mathutils import Vector
from numpy import *
try: from .numba_functions import numba_reaction_diffusion, numba_reaction_diffusion_anisotropic
except: pass
#from .numba_functions import numba_reaction_diffusion
try: import numexpr as ne
except: pass

# Reaction-Diffusion cache
from pathlib import Path
import random as rnd
import string

from bpy.types import (
        Operator,
        Panel,
        PropertyGroup,
        )

from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
    FloatVectorProperty,
    IntVectorProperty
)

from .utils import *

def reaction_diffusion_add_handler(self, context):
    # remove existing handlers
    old_handlers = []
    for h in bpy.app.handlers.frame_change_post:
        if "reaction_diffusion" in str(h):
            old_handlers.append(h)
    for h in old_handlers: bpy.app.handlers.frame_change_post.remove(h)
    # add new handler
    bpy.app.handlers.frame_change_post.append(reaction_diffusion_scene)

class formula_prop(PropertyGroup):
    name : StringProperty()
    formula : StringProperty()
    float_var : FloatVectorProperty(name="", description="", default=(0, 0, 0, 0, 0), size=5)
    int_var : IntVectorProperty(name="", description="", default=(0, 0, 0, 0, 0), size=5)

class reaction_diffusion_prop(PropertyGroup):
    run : BoolProperty(default=False, update = reaction_diffusion_add_handler,
        description='Compute a new iteration on frame changes. Currently is not working during  Render Animation')

    time_steps : IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps")

    dt : FloatProperty(
        name="dt", default=1, min=0, soft_max=0.2,
        description="Time Step")

    diff_a : FloatProperty(
        name="Diff A", default=0.1, min=0, soft_max=2, precision=3,
        description="Diffusion A")

    diff_b : FloatProperty(
        name="Diff B", default=0.05, min=0, soft_max=2, precision=3,
        description="Diffusion B")

    f : FloatProperty(
        name="f", default=0.055, soft_min=0.01, soft_max=0.06, precision=4, step=0.05,
        description="Feed Rate")

    k : FloatProperty(
        name="k", default=0.062, soft_min=0.035, soft_max=0.065, precision=4, step=0.05,
        description="Kill Rate")

    diff_mult : FloatProperty(
        name="Scale", default=1, min=0, soft_max=1, max=10, precision=2,
        description="Multiplier for the diffusion of both substances")

    vertex_group_diff_a : StringProperty(
        name="Diff A", default='',
        description="Vertex Group used for A diffusion")

    vertex_group_diff_b : StringProperty(
        name="Diff B", default='',
        description="Vertex Group used for B diffusion")

    vertex_group_scale : StringProperty(
        name="Scale", default='',
        description="Vertex Group used for Scale value")

    vertex_group_f : StringProperty(
        name="f", default='',
        description="Vertex Group used for Feed value (f)")

    vertex_group_k : StringProperty(
        name="k", default='',
        description="Vertex Group used for Kill value (k)")

    vertex_group_brush : StringProperty(
        name="Brush", default='',
        description="Vertex Group used for adding/removing B")

    invert_vertex_group_diff_a : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group Diff A')

    invert_vertex_group_diff_b : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group Diff B')

    invert_vertex_group_scale : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group Scale')

    invert_vertex_group_f : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group f')

    invert_vertex_group_k : BoolProperty(default=False,
        description='Inverte the value of the Vertex Group k')

    min_diff_a : FloatProperty(
        name="Min Diff A", default=0.1, min=0, soft_max=2, precision=3,
        description="Min Diff A")

    max_diff_a : FloatProperty(
        name="Max Diff A", default=0.1, min=0, soft_max=2, precision=3,
        description="Max Diff A")

    min_diff_b : FloatProperty(
        name="Min Diff B", default=0.1, min=0, soft_max=2, precision=3,
        description="Min Diff B")

    max_diff_b : FloatProperty(
        name="Max Diff B", default=0.1, min=0, soft_max=2, precision=3,
        description="Max Diff B")

    min_scale : FloatProperty(
        name="Scale", default=0.35, min=0, soft_max=1, max=10, precision=2,
        description="Min Scale Value")

    max_scale : FloatProperty(
        name="Scale", default=1, min=0, soft_max=1, max=10, precision=2,
        description="Max Scale value")

    min_f : FloatProperty(
        name="Min f", default=0.02, min=0, soft_min=0.01, soft_max=0.06, max=0.1, precision=4, step=0.05,
        description="Min Feed Rate")

    max_f : FloatProperty(
        name="Max f", default=0.055, min=0, soft_min=0.01, soft_max=0.06, max=0.1, precision=4, step=0.05,
        description="Max Feed Rate")

    min_k : FloatProperty(
        name="Min k", default=0.035, min=0, soft_min=0.035, soft_max=0.065, max=0.1, precision=4, step=0.05,
        description="Min Kill Rate")

    max_k : FloatProperty(
        name="Max k", default=0.062, min=0, soft_min=0.035, soft_max=0.065, max=0.1, precision=4, step=0.05,
        description="Max Kill Rate")

    brush_mult : FloatProperty(
        name="Mult", default=0.5, min=-1, max=1, precision=3, step=0.05,
        description="Multiplier for brush value")

    bool_mod : BoolProperty(
        name="Use Modifiers", default=False,
        description="Read modifiers affect the vertex groups")

    bool_cache : BoolProperty(
        name="Use Cache", default=False,
        description="Read modifiers affect the vertex groups")

    cache_frame_start : IntProperty(
        name="Start", default=1,
        description="Frame on which the simulation starts")

    cache_frame_end : IntProperty(
        name="End", default=250,
        description="Frame on which the simulation ends")

    cache_dir : StringProperty(
        name="Cache directory", default="", subtype='FILE_PATH',
        description = 'Directory that contains Reaction-Diffusion cache files'
        )

from numpy import *
def compute_formula(ob=None, formula="rx", float_var=(0,0,0,0,0), int_var=(0,0,0,0,0)):
    verts = ob.data.vertices
    n_verts = len(verts)

    f1,f2,f3,f4,f5 = float_var
    i1,i2,i3,i4,i5 = int_var

    do_groups = "w[" in formula
    do_local = "lx" in formula or "ly" in formula or "lz" in formula
    do_global = "gx" in formula or "gy" in formula or "gz" in formula
    do_relative = "rx" in formula or "ry" in formula or "rz" in formula
    do_normal = "nx" in formula or "ny" in formula or "nz" in formula
    mat = ob.matrix_world

    for i in range(1000):
        if "w["+str(i)+"]" in formula and i > len(ob.vertex_groups)-1:
            return "w["+str(i)+"] not found"

    w = []
    for i in range(len(ob.vertex_groups)):
        w.append([])
        if "w["+str(i)+"]" in formula:
            vg = ob.vertex_groups[i]
            for v in verts:
                try:
                    w[i].append(vg.weight(v.index))
                except:
                    w[i].append(0)
            w[i] = array(w[i])

    start_time = timeit.default_timer()
    # compute vertex coordinates
    if do_local or do_relative or do_global:
        co = [0]*n_verts*3
        verts.foreach_get('co', co)
        np_co = array(co).reshape((n_verts, 3))
        lx, ly, lz = array(np_co).transpose()
        if do_relative:
            rx = np.interp(lx, (lx.min(), lx.max()), (0, +1))
            ry = np.interp(ly, (ly.min(), ly.max()), (0, +1))
            rz = np.interp(lz, (lz.min(), lz.max()), (0, +1))
        if do_global:
            co = [v.co for v in verts]
            global_co = []
            for v in co:
                global_co.append(mat @ v)
            global_co = array(global_co).reshape((n_verts, 3))
            gx, gy, gz = array(global_co).transpose()
    # compute vertex normals
    if do_normal:
        normal = [0]*n_verts*3
        verts.foreach_get('normal', normal)
        normal = array(normal).reshape((n_verts, 3))
        nx, ny, nz = array(normal).transpose()

    try:
        weight = eval(formula)
        return weight
    except:
        return "There is something wrong"
    print("Weight Formula: " + str(timeit.default_timer() - start_time))

class weight_formula_wiki(Operator):
    bl_idname = "scene.weight_formula_wiki"
    bl_label = "Online Documentation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.wm.url_open(url="https://github.com/alessandro-zomparelli/tissue/wiki/Weight-Tools#weight-formula")
        return {'FINISHED'}

class weight_formula(Operator):
    bl_idname = "object.weight_formula"
    bl_label = "Weight Formula"
    bl_description = "Generate a Vertex Group according to a mathematical formula"
    bl_options = {'REGISTER', 'UNDO'}

    ex = [
        #'cos(arctan(nx/ny)*6 + sin(rz*30)*0.5)/2 + cos(arctan(nx/ny)*6 - sin(rz*30)*0.5 + pi/2)/2 + 0.5',
        'cos(arctan(nx/ny)*i1*2 + sin(rz*i3))/i2 + cos(arctan(nx/ny)*i1*2 - sin(rz*i3))/i2 + 0.5',
        'cos(arctan(nx/ny)*i1*2 + sin(rz*i2))/2 + cos(arctan(nx/ny)*i1*2 - sin(rz*i2))/2',
        '(sin(arctan(nx/ny)*i1)*sin(nz*i1)+1)/2',
        'cos(arctan(nx/ny)*f1)',
        'cos(arctan(lx/ly)*f1 + sin(rz*f2)*f3)',
        'sin(nx*15)<sin(ny*15)',
        'cos(ny*rz**2*i1)',
        'sin(rx*30) > 0',
        'sin(nz*i1)',
        'w[0]**2',
        'sqrt((rx-0.5)**2 + (ry-0.5)**2)*2',
        'abs(0.5-rz)*2',
        'rx'
        ]
    ex_items = list((str(i),s,"") for i,s in enumerate(ex))
    ex_items.append(('CUSTOM', "User Formula", ""))

    examples : EnumProperty(
        items = ex_items, default='CUSTOM', name="Examples")

    old_ex = ""

    formula : StringProperty(
        name="Formula", default="", description="Formula to Evaluate")

    slider_f01 : FloatProperty(
        name="f1", default=1, description="Slider Float 1")
    slider_f02 : FloatProperty(
        name="f2", default=1, description="Slider Float 2")
    slider_f03 : FloatProperty(
        name="f3", default=1, description="Slider Float 3")
    slider_f04 : FloatProperty(
        name="f4", default=1, description="Slider Float 4")
    slider_f05 : FloatProperty(
        name="f5", default=1, description="Slider Float 5")
    slider_i01 : IntProperty(
        name="i1", default=1, description="Slider Integer 1")
    slider_i02 : IntProperty(
        name="i2", default=1, description="Slider Integer 2")
    slider_i03 : IntProperty(
        name="i3", default=1, description="Slider Integer 3")
    slider_i04 : IntProperty(
        name="i4", default=1, description="Slider Integer 4")
    slider_i05 : IntProperty(
        name="i5", default=1, description="Slider Integer 5")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        #layout.label(text="Examples")
        layout.prop(self, "examples", text="Examples")
        #if self.examples == 'CUSTOM':
        layout.label(text="Formula")
        layout.prop(self, "formula", text="")
        #try: self.examples = self.formula
        #except: pass

        if self.examples != 'CUSTOM':
            example = self.ex[int(self.examples)]
            if example != self.old_ex:
                self.formula = example
                self.old_ex = example
            elif self.formula != example:
                self.examples = 'CUSTOM'
        formula = self.formula

        layout.separator()
        if "f1" in formula: layout.prop(self, "slider_f01")
        if "f2" in formula: layout.prop(self, "slider_f02")
        if "f3" in formula: layout.prop(self, "slider_f03")
        if "f4" in formula: layout.prop(self, "slider_f04")
        if "f5" in formula: layout.prop(self, "slider_f05")
        if "i1" in formula: layout.prop(self, "slider_i01")
        if "i2" in formula: layout.prop(self, "slider_i02")
        if "i3" in formula: layout.prop(self, "slider_i03")
        if "i4" in formula: layout.prop(self, "slider_i04")
        if "i5" in formula: layout.prop(self, "slider_i05")

        layout.label(text="Variables (for each vertex):")
        layout.label(text="lx, ly, lz: Local Coordinates", icon='ORIENTATION_LOCAL')
        layout.label(text="gx, gy, gz: Global Coordinates", icon='WORLD')
        layout.label(text="rx, ry, rz: Local Coordinates (0 to 1)", icon='NORMALIZE_FCURVES')
        layout.label(text="nx, ny, nz: Normal Coordinates", icon='SNAP_NORMAL')
        layout.label(text="w[0], w[1], w[2], ... : Vertex Groups", icon="GROUP_VERTEX")
        layout.separator()
        layout.label(text="f1, f2, f3, f4, f5: Float Sliders", icon='MOD_HUE_SATURATION')#PROPERTIES
        layout.label(text="i1, i2, i3, i4, i5: Integer Sliders", icon='MOD_HUE_SATURATION')
        layout.separator()
        #layout.label(text="All mathematical functions are based on Numpy", icon='INFO')
        #layout.label(text="https://docs.scipy.org/doc/numpy-1.13.0/reference/routines.math.html", icon='INFO')
        layout.operator("scene.weight_formula_wiki", icon="HELP")
        #layout.label(text="(where 'i' is the index of the Vertex Group)")

    def execute(self, context):
        ob = context.active_object
        n_verts = len(ob.data.vertices)
        #if self.examples == 'CUSTOM':
        #    formula = self.formula
        #else:
        #self.formula = self.examples
        #    formula = self.examples

        #f1, f2, f3, f4, f5 = self.slider_f01, self.slider_f02, self.slider_f03, self.slider_f04, self.slider_f05
        #i1, i2, i3, i4, i5 = self.slider_i01, self.slider_i02, self.slider_i03, self.slider_i04, self.slider_i05
        f_sliders = self.slider_f01, self.slider_f02, self.slider_f03, self.slider_f04, self.slider_f05
        i_sliders = self.slider_i01, self.slider_i02, self.slider_i03, self.slider_i04, self.slider_i05

        if self.examples != 'CUSTOM':
            example = self.ex[int(self.examples)]
            if example != self.old_ex:
                self.formula = example
                self.old_ex = example
            elif self.formula != example:
                self.examples = 'CUSTOM'
        formula = self.formula

        if formula == "": return {'FINISHED'}
        # replace numeric sliders value
        for i, slider in enumerate(f_sliders):
            formula = formula.replace('f'+str(i+1),"{0:.2f}".format(slider))
        for i, slider in enumerate(i_sliders):
            formula =formula.replace('i'+str(i+1),str(slider))
        vertex_group_name = "" + formula
        ob.vertex_groups.new(name=vertex_group_name)

        weight = compute_formula(ob, formula=formula, float_var=f_sliders, int_var=i_sliders)
        if type(weight) == str:
            self.report({'ERROR'}, weight)
            return {'CANCELLED'}

        #start_time = timeit.default_timer()
        weight = nan_to_num(weight)
        vg = ob.vertex_groups[-1]
        if type(weight) == int or type(weight) == float:
            for i in range(n_verts):
                vg.add([i], weight, 'REPLACE')
        elif type(weight) == ndarray:
            for i in range(n_verts):
                vg.add([i], weight[i], 'REPLACE')
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        # Store formula settings
        new_formula = ob.formula_settings.add()
        new_formula.name = ob.vertex_groups[-1].name
        new_formula.formula = formula
        new_formula.int_var = i_sliders
        new_formula.float_var = f_sliders

        #for f in ob.formula_settings:
        #    print(f.name, f.formula, f.int_var, f.float_var)
        return {'FINISHED'}


class update_weight_formula(Operator):
    bl_idname = "object.update_weight_formula"
    bl_label = "Update Weight Formula"
    bl_description = "Update an existing Vertex Group. Make sure that the name\nof the active Vertex Group is a valid formula"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        ob = context.active_object
        n_verts = len(ob.data.vertices)

        vg = ob.vertex_groups.active
        formula = vg.name
        weight = compute_formula(ob, formula=formula)
        if type(weight) == str:
            self.report({'ERROR'}, "The name of the active Vertex Group\nis not a valid Formula")
            return {'CANCELLED'}

        #start_time = timeit.default_timer()
        weight = nan_to_num(weight)
        if type(weight) == int or type(weight) == float:
            for i in range(n_verts):
                vg.add([i], weight, 'REPLACE')
        elif type(weight) == ndarray:
            for i in range(n_verts):
                vg.add([i], weight[i], 'REPLACE')
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}


class _weight_laplacian(Operator):
    bl_idname = "object._weight_laplacian"
    bl_label = "Weight Laplacian"
    bl_description = ("Compute the Vertex Group Laplacian")
    bl_options = {'REGISTER', 'UNDO'}

    bounds : EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('POSITIVE', "Positive Only", ""),
            ('NEGATIVE', "Negative Only", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    mode : EnumProperty(
        items=(('LENGTH', "Length Weight", ""),
            ('SIMPLE', "Simple", "")),
        default='SIMPLE', name="Evaluation Mode")

    min_def : FloatProperty(
        name="Min", default=0, soft_min=-1, soft_max=0,
        description="Laplacian value with 0 weight")

    max_def : FloatProperty(
        name="Max", default=0.5, soft_min=0, soft_max=5,
        description="Laplacian value with 1 weight")

    bounds_string = ""

    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Evaluation Mode")
        col.prop(self, "mode", text="")
        col.label(text="Bounds")
        col.prop(self, "bounds", text="")
        if self.bounds == 'MANUAL':
            col.label(text="Strain Rate \u03B5:")
            col.prop(self, "min_def")
            col.prop(self, "max_def")
        col.label(text="\u03B5" + ": from " + self.bounds_string)


    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        group_id = ob.vertex_groups.active_index
        input_group = ob.vertex_groups[group_id].name

        group_name = "Laplacian"
        ob.vertex_groups.new(name=group_name)
        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()

        # store weight values
        weight = []
        for v in me.vertices:
            try:
                weight.append(ob.vertex_groups[input_group].weight(v.index))
            except:
                weight.append(0)

        n_verts = len(bm.verts)
        lap = [0]*n_verts
        for e in bm.edges:
            if self.mode == 'LENGTH':
                length = e.calc_length()
                if length == 0: continue
                id0 = e.verts[0].index
                id1 = e.verts[1].index
                lap[id0] += weight[id1]/length - weight[id0]/length
                lap[id1] += weight[id0]/length - weight[id1]/length
            else:
                id0 = e.verts[0].index
                id1 = e.verts[1].index
                lap[id0] += weight[id1] - weight[id0]
                lap[id1] += weight[id0] - weight[id1]

        mean_lap = mean(lap)
        stdev_lap = stdev(lap)
        filter_lap = [i for i in lap if mean_lap-2*stdev_lap < i < mean_lap+2*stdev_lap]
        if self.bounds == 'MANUAL':
            min_def = self.min_def
            max_def = self.max_def
        elif self.bounds == 'AUTOMATIC':
            min_def = min(filter_lap)
            max_def = max(filter_lap)
            self.min_def = min_def
            self.max_def = max_def
        elif self.bounds == 'NEGATIVE':
            min_def = 0
            max_def = min(filter_lap)
            self.min_def = min_def
            self.max_def = max_def
        elif self.bounds == 'POSITIVE':
            min_def = 0
            max_def = max(filter_lap)
            self.min_def = min_def
            self.max_def = max_def
        delta_def = max_def - min_def

        # check undeformed errors
        if delta_def == 0: delta_def = 0.0001

        for i in range(len(lap)):
            val = (lap[i]-min_def)/delta_def
            if val > 0.7: print(str(val) + " " + str(lap[i]))
            #val = weight[i] + 0.2*lap[i]
            ob.vertex_groups[-1].add([i], val, 'REPLACE')
        self.bounds_string = str(round(min_def,2)) + " to " + str(round(max_def,2))
        ob.vertex_groups[-1].name = group_name + " " + self.bounds_string
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bm.free()
        return {'FINISHED'}

class ok_weight_laplacian(Operator):
    bl_idname = "object.weight_laplacian"
    bl_label = "Weight Laplacian"
    bl_description = ("Compute the Vertex Group Laplacian")
    bl_options = {'REGISTER', 'UNDO'}

    bounds_string = ""

    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0


    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()

        group_id = ob.vertex_groups.active_index
        input_group = ob.vertex_groups[group_id].name

        group_name = "Laplacian"
        ob.vertex_groups.new(name=group_name)

        # store weight values
        a = []
        for v in me.vertices:
            try:
                a.append(ob.vertex_groups[input_group].weight(v.index))
            except:
                a.append(0)

        a = array(a)


        # initialize
        n_verts = len(bm.verts)
        # find max number of edges for vertex
        max_edges = 0
        n_neighbors = []
        id_neighbors = []
        for v in bm.verts:
            n_edges = len(v.link_edges)
            max_edges = max(max_edges, n_edges)
            n_neighbors.append(n_edges)
            neighbors = []
            for e in v.link_edges:
                for v1 in e.verts:
                    if v != v1: neighbors.append(v1.index)
            id_neighbors.append(neighbors)
        n_neighbors = array(n_neighbors)


        lap_map = [[] for i in range(n_verts)]
        #lap_map = []
        '''
        for e in bm.edges:
            id0 = e.verts[0].index
            id1 = e.verts[1].index
            lap_map[id0].append(id1)
            lap_map[id1].append(id0)
        '''
        lap = zeros((n_verts))#[0]*n_verts
        n_records = zeros((n_verts))
        for e in bm.edges:
            id0 = e.verts[0].index
            id1 = e.verts[1].index
            length = e.calc_length()
            if length == 0: continue
            #lap[id0] += abs(a[id1] - a[id0])/length
            #lap[id1] += abs(a[id0] - a[id1])/length
            lap[id0] += (a[id1] - a[id0])/length
            lap[id1] += (a[id0] - a[id1])/length
            n_records[id0]+=1
            n_records[id1]+=1
        lap /= n_records
        lap /= max(lap)

        for i in range(n_verts):
            ob.vertex_groups['Laplacian'].add([i], lap[i], 'REPLACE')
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bm.free()
        return {'FINISHED'}

class weight_laplacian(Operator):
    bl_idname = "object.weight_laplacian"
    bl_label = "Weight Laplacian"
    bl_description = ("Compute the Vertex Group Laplacian")
    bl_options = {'REGISTER', 'UNDO'}

    bounds_string = ""

    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0


    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()
        n_verts = len(me.vertices)

        group_id = ob.vertex_groups.active_index
        input_group = ob.vertex_groups[group_id].name

        group_name = "Laplacian"
        vg = ob.vertex_groups.new(name=group_name)

        # store weight values
        dvert_lay = bm.verts.layers.deform.active
        weight = bmesh_get_weight_numpy(group_id, dvert_lay, bm.verts)

        #verts, normals = get_vertices_and_normals_numpy(me)

        #lap = zeros((n_verts))#[0]*n_verts
        lap = [Vector((0,0,0)) for i in range(n_verts)]
        n_records = zeros((n_verts))
        for e in bm.edges:
            vert0 = e.verts[0]
            vert1 = e.verts[1]
            id0 = vert0.index
            id1 = vert1.index
            v0 = vert0.co
            v1 = vert1.co
            v01 = v1-v0
            v10 = -v01
            v01 -= v01.project(vert0.normal)
            v10 -= v10.project(vert1.normal)
            length = e.calc_length()
            if length == 0: continue
            dw = (weight[id1] - weight[id0])/length
            lap[id0] += v01.normalized() * dw
            lap[id1] -= v10.normalized() * dw
            n_records[id0]+=1
            n_records[id1]+=1
        #lap /= n_records[:,np.newaxis]
        lap = [l.length/r for r,l in zip(n_records,lap)]

        lap = np.array(lap)
        lap /= np.max(lap)
        lap = list(lap)
        print(lap)

        for i in range(n_verts):
            vg.add([i], lap[i], 'REPLACE')
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bm.free()
        return {'FINISHED'}


class reaction_diffusion(Operator):
    bl_idname = "object.reaction_diffusion"
    bl_label = "Reaction Diffusion"
    bl_description = ("Run a Reaction-Diffusion based on existing Vertex Groups: A and B")
    bl_options = {'REGISTER', 'UNDO'}

    steps : IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps")

    dt : FloatProperty(
        name="dt", default=0.2, min=0, soft_max=0.2,
        description="Time Step")

    diff_a : FloatProperty(
        name="Diff A", default=1, min=0, soft_max=2,
        description="Diffusion A")

    diff_b : FloatProperty(
        name="Diff B", default=0.5, min=0, soft_max=2,
        description="Diffusion B")

    f : FloatProperty(
        name="f", default=0.055, min=0, soft_min=0.01, soft_max=0.06, max=0.1, precision=4,
        description="Feed Rate")

    k : FloatProperty(
        name="k", default=0.062, min=0, soft_min=0.035, soft_max=0.065, max=0.1, precision=4,
        description="Kill Rate")

    bounds_string = ""

    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0


    def execute(self, context):
        #bpy.app.handlers.frame_change_post.remove(reaction_diffusion_def)
        reaction_diffusion_add_handler(self, context)
        set_animatable_fix_handler(self, context)
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()

        # store weight values
        a = []
        b = []
        for v in me.vertices:
            try:
                a.append(ob.vertex_groups["A"].weight(v.index))
            except:
                a.append(0)
            try:
                b.append(ob.vertex_groups["B"].weight(v.index))
            except:
                b.append(0)

        a = array(a)
        b = array(b)
        f = self.f
        k = self.k
        diff_a = self.diff_a
        diff_b = self.diff_b
        dt = self.dt
        n_verts = len(bm.verts)

        for i in range(self.steps):

            lap_a = zeros((n_verts))#[0]*n_verts
            lap_b = zeros((n_verts))#[0]*n_verts
            for e in bm.edges:
                id0 = e.verts[0].index
                id1 = e.verts[1].index
                lap_a[id0] += a[id1] - a[id0]
                lap_a[id1] += a[id0] - a[id1]
                lap_b[id0] += b[id1] - b[id0]
                lap_b[id1] += b[id0] - b[id1]
            ab2 = a*b**2
            a += (diff_a*lap_a - ab2 + f*(1-a))*dt
            b += (diff_b*lap_b + ab2 - (k+f)*b)*dt

            for i in range(n_verts):
                ob.vertex_groups['A'].add([i], a[i], 'REPLACE')
                ob.vertex_groups['B'].add([i], b[i], 'REPLACE')
            ob.vertex_groups.update()
            ob.data.update()

            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bm.free()
        return {'FINISHED'}


class edges_deformation(Operator):
    bl_idname = "object.edges_deformation"
    bl_label = "Edges Deformation"
    bl_description = ("Compute Weight based on the deformation of edges"+
        "according to visible modifiers.")
    bl_options = {'REGISTER', 'UNDO'}

    bounds : EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('COMPRESSION', "Compressed Only", ""),
            ('TENSION', "Extended Only", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    mode : EnumProperty(
        items=(('MAX', "Max Deformation", ""),
            ('MEAN', "Average Deformation", "")),
        default='MEAN', name="Evaluation Mode")

    min_def : FloatProperty(
        name="Min", default=0, soft_min=-1, soft_max=0,
        description="Deformations with 0 weight")

    max_def : FloatProperty(
        name="Max", default=0.5, soft_min=0, soft_max=5,
        description="Deformations with 1 weight")

    bounds_string = ""

    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.modifiers) > 0

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Evaluation Mode")
        col.prop(self, "mode", text="")
        col.label(text="Bounds")
        col.prop(self, "bounds", text="")
        if self.bounds == 'MANUAL':
            col.label(text="Strain Rate \u03B5:")
            col.prop(self, "min_def")
            col.prop(self, "max_def")
        col.label(text="\u03B5" + ": from " + self.bounds_string)

    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        # check if the object is Cloth or Softbody
        physics = False
        for m in ob.modifiers:
            if m.type == 'CLOTH' or m.type == 'SOFT_BODY':
                physics = True
                if context.scene.frame_current == 1 and self.frame != None:
                    context.scene.frame_current = self.frame
                break
        if not physics: self.frame = None

        if self.mode == 'MEAN': group_name = "Average Deformation"
        elif self.mode == 'MAX': group_name = "Max Deformation"
        ob.vertex_groups.new(name=group_name)
        me0 = ob.data

        me = simple_to_mesh(ob) #ob.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
        if len(me.vertices) != len(me0.vertices) or len(me.edges) != len(me0.edges):
            self.report({'ERROR'}, "The topology of the object should be" +
                "unaltered")
            return {'CANCELLED'}

        bm0 = bmesh.new()
        bm0.from_mesh(me0)
        bm = bmesh.new()
        bm.from_mesh(me)
        deformations = []
        for e0, e in zip(bm0.edges, bm.edges):
            try:
                l0 = e0.calc_length()
                l1 = e.calc_length()
                epsilon = (l1 - l0)/l0
                deformations.append(epsilon)
            except: deformations.append(1)
        v_deformations = []
        for v in bm.verts:
            vdef = []
            for e in v.link_edges:
                vdef.append(deformations[e.index])
            if self.mode == 'MEAN': v_deformations.append(mean(vdef))
            elif self.mode == 'MAX': v_deformations.append(max(vdef, key=abs))
            #elif self.mode == 'MIN': v_deformations.append(min(vdef, key=abs))

        if self.bounds == 'MANUAL':
            min_def = self.min_def
            max_def = self.max_def
        elif self.bounds == 'AUTOMATIC':
            min_def = min(v_deformations)
            max_def = max(v_deformations)
            self.min_def = min_def
            self.max_def = max_def
        elif self.bounds == 'COMPRESSION':
            min_def = 0
            max_def = min(v_deformations)
            self.min_def = min_def
            self.max_def = max_def
        elif self.bounds == 'TENSION':
            min_def = 0
            max_def = max(v_deformations)
            self.min_def = min_def
            self.max_def = max_def
        delta_def = max_def - min_def

        # check undeformed errors
        if delta_def == 0:
            if self.bounds == 'MANUAL':
                delta_def = 0.0001
            else:
                message = "The object doesn't have deformations."
                if physics:
                    message = message + ("\nIf you are using Physics try to " +
                        "save it in the cache before.")
                self.report({'ERROR'}, message)
                return {'CANCELLED'}
        else:
            if physics:
                self.frame = context.scene.frame_current

        for i in range(len(v_deformations)):
            weight = (v_deformations[i] - min_def)/delta_def
            ob.vertex_groups[-1].add([i], weight, 'REPLACE')
        self.bounds_string = str(round(min_def,2)) + " to " + str(round(max_def,2))
        ob.vertex_groups[-1].name = group_name + " " + self.bounds_string
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bpy.data.meshes.remove(me)
        bm.free()
        bm0.free()
        return {'FINISHED'}

class edges_bending(Operator):
    bl_idname = "object.edges_bending"
    bl_label = "Edges Bending"
    bl_description = ("Compute Weight based on the bending of edges"+
        "according to visible modifiers.")
    bl_options = {'REGISTER', 'UNDO'}

    bounds : EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('POSITIVE', "Positive Only", ""),
            ('NEGATIVE', "Negative Only", ""),
            ('UNSIGNED', "Absolute Bending", ""),
            ('AUTOMATIC', "Signed Bending", "")),
        default='AUTOMATIC', name="Bounds")

    min_def : FloatProperty(
        name="Min", default=-10, soft_min=-45, soft_max=45,
        description="Deformations with 0 weight")

    max_def : FloatProperty(
        name="Max", default=10, soft_min=-45, soft_max=45,
        description="Deformations with 1 weight")

    bounds_string = ""
    frame = None

    @classmethod
    def poll(cls, context):
        return len(context.object.modifiers) > 0

    def draw(self, context):
        layout = self.layout
        layout.label(text="Bounds")
        layout.prop(self, "bounds", text="")
        if self.bounds == 'MANUAL':
            layout.prop(self, "min_def")
            layout.prop(self, "max_def")

    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}

        group_name = "Edges Bending"
        ob.vertex_groups.new(name=group_name)

        # check if the object is Cloth or Softbody
        physics = False
        for m in ob.modifiers:
            if m.type == 'CLOTH' or m.type == 'SOFT_BODY':
                physics = True
                if context.scene.frame_current == 1 and self.frame != None:
                    context.scene.frame_current = self.frame
                break
        if not physics: self.frame = None

        #ob.data.update()
        #context.scene.update()
        me0 = ob.data
        me = simple_to_mesh(ob) #ob.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
        if len(me.vertices) != len(me0.vertices) or len(me.edges) != len(me0.edges):
            self.report({'ERROR'}, "The topology of the object should be" +
                "unaltered")
        bm0 = bmesh.new()
        bm0.from_mesh(me0)
        bm = bmesh.new()
        bm.from_mesh(me)
        deformations = []
        for e0, e in zip(bm0.edges, bm.edges):
            try:
                ang = e.calc_face_angle_signed()
                ang0 = e0.calc_face_angle_signed()
                if self.bounds == 'UNSIGNED':
                    deformations.append(abs(ang-ang0))
                else:
                    deformations.append(ang-ang0)
            except: deformations.append(0)
        v_deformations = []
        for v in bm.verts:
            vdef = []
            for e in v.link_edges:
                vdef.append(deformations[e.index])
            v_deformations.append(mean(vdef))
        if self.bounds == 'MANUAL':
            min_def = radians(self.min_def)
            max_def = radians(self.max_def)
        elif self.bounds == 'AUTOMATIC':
            min_def = min(v_deformations)
            max_def = max(v_deformations)
        elif self.bounds == 'POSITIVE':
            min_def = 0
            max_def = min(v_deformations)
        elif self.bounds == 'NEGATIVE':
            min_def = 0
            max_def = max(v_deformations)
        elif self.bounds == 'UNSIGNED':
            min_def = 0
            max_def = max(v_deformations)
        delta_def = max_def - min_def

        # check undeformed errors
        if delta_def == 0:
            if self.bounds == 'MANUAL':
                delta_def = 0.0001
            else:
                message = "The object doesn't have deformations."
                if physics:
                    message = message + ("\nIf you are using Physics try to " +
                        "save it in the cache before.")
                self.report({'ERROR'}, message)
                return {'CANCELLED'}
        else:
            if physics:
                self.frame = context.scene.frame_current

        for i in range(len(v_deformations)):
            weight = (v_deformations[i] - min_def)/delta_def
            ob.vertex_groups[-1].add([i], weight, 'REPLACE')
        self.bounds_string = str(round(min_def,2)) + " to " + str(round(max_def,2))
        ob.vertex_groups[-1].name = group_name + " " + self.bounds_string
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bpy.data.meshes.remove(me)
        bm0.free()
        bm.free()
        return {'FINISHED'}

class weight_contour_displace(Operator):
    bl_idname = "object.weight_contour_displace"
    bl_label = "Contour Displace"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")
    min_iso : FloatProperty(
        name="Min Iso Value", default=0.49, min=0, max=1,
        description="Threshold value")
    max_iso : FloatProperty(
        name="Max Iso Value", default=0.51, min=0, max=1,
        description="Threshold value")
    n_cuts : IntProperty(
        name="Cuts", default=2, min=1, soft_max=10,
        description="Number of cuts in the selected range of values")
    bool_displace : BoolProperty(
        name="Add Displace", default=True, description="Add Displace Modifier")
    bool_flip : BoolProperty(
        name="Flip", default=False, description="Flip Output Weight")

    weight_mode : EnumProperty(
        items=[('Remapped', 'Remapped', 'Remap values'),
               ('Alternate', 'Alternate', 'Alternate 0 and 1'),
               ('Original', 'Original', 'Keep original Vertex Group')],
        name="Weight", description="Choose how to convert vertex group",
        default="Remapped", options={'LIBRARY_EDITABLE'})

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}

        ob0 = context.object

        group_id = ob0.vertex_groups.active_index
        vertex_group_name = ob0.vertex_groups[group_id].name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        if self.use_modifiers:
            #me0 = ob0.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
            me0 = simple_to_mesh(ob0)
        else:
            me0 = ob0.data.copy()

        # generate new bmesh
        bm = bmesh.new()
        bm.from_mesh(me0)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # store weight values
        weight = []
        ob = bpy.data.objects.new("temp", me0)
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)
        for v in me0.vertices:
            try:
                weight.append(ob.vertex_groups[vertex_group_name].weight(v.index))
            except:
                weight.append(0)

        # define iso values
        iso_values = []
        for i_cut in range(self.n_cuts):
            delta_iso = abs(self.max_iso - self.min_iso)
            min_iso = min(self.min_iso, self.max_iso)
            max_iso = max(self.min_iso, self.max_iso)
            if delta_iso == 0: iso_val = min_iso
            elif self.n_cuts > 1: iso_val = i_cut/(self.n_cuts-1)*delta_iso + min_iso
            else: iso_val = (self.max_iso + self.min_iso)/2
            iso_values.append(iso_val)

        # Start Cuts Iterations
        filtered_edges = bm.edges
        for iso_val in iso_values:
            delete_edges = []

            faces_mask = []
            for f in bm.faces:
                w_min = 2
                w_max = 2
                for v in f.verts:
                    w = weight[v.index]
                    if w_min == 2:
                        w_max = w_min = w
                    if w > w_max: w_max = w
                    if w < w_min: w_min = w
                    if w_min < iso_val and w_max > iso_val:
                        faces_mask.append(f)
                        break

            #link_faces = [[f for f in e.link_faces] for e in bm.edges]

            #faces_todo = [f.select for f in bm.faces]
            #faces_todo = [True for f in bm.faces]
            verts = []
            edges = []
            edges_id = {}
            _filtered_edges = []
            n_verts = len(bm.verts)
            count = n_verts
            for e in filtered_edges:
                #id0 = e.vertices[0]
                #id1 = e.vertices[1]
                id0 = e.verts[0].index
                id1 = e.verts[1].index
                w0 = weight[id0]
                w1 = weight[id1]

                if w0 == w1: continue
                elif w0 > iso_val and w1 > iso_val:
                    _filtered_edges.append(e)
                    continue
                elif w0 < iso_val and w1 < iso_val: continue
                elif w0 == iso_val or w1 == iso_val:
                    _filtered_edges.append(e)
                    continue
                else:
                    v0 = bm.verts[id0].co
                    v1 = bm.verts[id1].co
                    v = v0.lerp(v1, (iso_val-w0)/(w1-w0))
                    if e not in delete_edges:
                        delete_edges.append(e)
                    verts.append(v)
                    edges_id[str(id0)+"_"+str(id1)] = count
                    edges_id[str(id1)+"_"+str(id0)] = count
                    count += 1
                    _filtered_edges.append(e)
            filtered_edges = _filtered_edges
            splitted_faces = []

            switch = False
            # splitting faces
            for f in faces_mask:
                # create sub-faces slots. Once a new vertex is reached it will
                # change slot, storing the next vertices for a new face.
                build_faces = [[],[]]
                #switch = False
                verts0 = [v.index for v in f.verts]
                verts1 = list(verts0)
                verts1.append(verts1.pop(0)) # shift list
                for id0, id1 in zip(verts0, verts1):

                    # add first vertex to active slot
                    build_faces[switch].append(id0)

                    # try to split edge
                    try:
                        # check if the edge must be splitted
                        new_vert = edges_id[str(id0)+"_"+str(id1)]
                        # add new vertex
                        build_faces[switch].append(new_vert)
                        # if there is an open face on the other slot
                        if len(build_faces[not switch]) > 0:
                            # store actual face
                            splitted_faces.append(build_faces[switch])
                            # reset actual faces and switch
                            build_faces[switch] = []
                            # change face slot
                        switch = not switch
                        # continue previous face
                        build_faces[switch].append(new_vert)
                    except: pass
                if len(build_faces[not switch]) == 2:
                    build_faces[not switch].append(id0)
                if len(build_faces[not switch]) > 2:
                    splitted_faces.append(build_faces[not switch])
                # add last face
                splitted_faces.append(build_faces[switch])
                #del_faces.append(f.index)

            # adding new vertices
            _new_vert = bm.verts.new
            for v in verts: new_vert = _new_vert(v)
            bm.verts.index_update()
            bm.verts.ensure_lookup_table()
            # adding new faces
            _new_face = bm.faces.new
            missed_faces = []
            added_faces = []
            for f in splitted_faces:
                try:
                    face_verts = [bm.verts[i] for i in f]
                    new_face = _new_face(face_verts)
                    for e in new_face.edges:
                        filtered_edges.append(e)
                except:
                    missed_faces.append(f)

            bm.faces.ensure_lookup_table()
            # updating weight values
            weight = weight + [iso_val]*len(verts)

            # deleting old edges/faces
            _remove_edge = bm.edges.remove
            bm.edges.ensure_lookup_table()
            for e in delete_edges:
                _remove_edge(e)
            _filtered_edges = []
            for e in filtered_edges:
                if e not in delete_edges: _filtered_edges.append(e)
            filtered_edges = _filtered_edges

        name = ob0.name + '_ContourDisp'
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)

        # Link object to scene and make active
        scn = context.scene
        context.collection.objects.link(ob)
        context.view_layer.objects.active = ob
        ob.select_set(True)
        ob0.select_set(False)

        # generate new vertex group
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)
        #ob.vertex_groups.new(name=vertex_group_name)

        all_weight = weight + [iso_val]*len(verts)
        #mult = 1/(1-iso_val)
        for id in range(len(all_weight)):
            #if False: w = (all_weight[id]-iso_val)*mult
            w = all_weight[id]
            if self.weight_mode == 'Alternate':
                direction = self.bool_flip
                for i in range(len(iso_values)-1):
                    val0, val1 = iso_values[i], iso_values[i+1]
                    if val0 < w <= val1:
                        if direction: w1 = (w-val0)/(val1-val0)
                        else: w1 = (val1-w)/(val1-val0)
                    direction = not direction
                if w < iso_values[0]: w1 = not self.bool_flip
                if w > iso_values[-1]: w1 = not direction
            elif self.weight_mode == 'Remapped':
                if w < min_iso: w1 = 0
                elif w > max_iso: w1 = 1
                else: w1 = (w - min_iso)/delta_iso
            else:
                if self.bool_flip: w1 = 1-w
                else: w1 = w
            ob.vertex_groups[vertex_group_name].add([id], w1, 'REPLACE')

        ob.vertex_groups.active_index = group_id

        # align new object
        ob.matrix_world = ob0.matrix_world

        # Displace Modifier
        if self.bool_displace:
            ob.modifiers.new(type='DISPLACE', name='Displace')
            ob.modifiers["Displace"].mid_level = 0
            ob.modifiers["Displace"].strength = 0.1
            ob.modifiers['Displace'].vertex_group = vertex_group_name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        print("Contour Displace time: " + str(timeit.default_timer() - start_time) + " sec")

        bpy.data.meshes.remove(me0)

        return {'FINISHED'}

class weight_contour_mask(Operator):
    bl_idname = "object.weight_contour_mask"
    bl_label = "Contour Mask"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")
    iso : FloatProperty(
        name="Iso Value", default=0.5, soft_min=0, soft_max=1,
        description="Threshold value")
    bool_solidify : BoolProperty(
        name="Solidify", default=True, description="Add Solidify Modifier")
    normalize_weight : BoolProperty(
        name="Normalize Weight", default=True,
        description="Normalize weight of remaining vertices")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}

        ob0 = bpy.context.object

        iso_val = self.iso
        group_id = ob0.vertex_groups.active_index
        vertex_group_name = ob0.vertex_groups[group_id].name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        if self.use_modifiers:
            me0 = simple_to_mesh(ob0)#ob0.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
        else:
            me0 = ob0.data.copy()

        # generate new bmesh
        bm = bmesh.new()
        bm.from_mesh(me0)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # store weight values
        weight = []
        ob = bpy.data.objects.new("temp", me0)
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)
        for v in me0.vertices:
            try:
                #weight.append(v.groups[vertex_group_name].weight)
                weight.append(ob.vertex_groups[vertex_group_name].weight(v.index))
            except:
                weight.append(0)

        faces_mask = []
        for f in bm.faces:
            w_min = 2
            w_max = 2
            for v in f.verts:
                w = weight[v.index]
                if w_min == 2:
                    w_max = w_min = w
                if w > w_max: w_max = w
                if w < w_min: w_min = w
                if w_min < iso_val and w_max > iso_val:
                    faces_mask.append(f)
                    break

        filtered_edges = bm.edges# me0.edges
        faces_todo = [f.select for f in bm.faces]
        verts = []
        edges = []
        delete_edges = []
        edges_id = {}
        _filtered_edges = []
        n_verts = len(bm.verts)
        count = n_verts
        for e in filtered_edges:
            id0 = e.verts[0].index
            id1 = e.verts[1].index
            w0 = weight[id0]
            w1 = weight[id1]

            if w0 == w1: continue
            elif w0 > iso_val and w1 > iso_val:
                continue
            elif w0 < iso_val and w1 < iso_val: continue
            elif w0 == iso_val or w1 == iso_val: continue
            else:
                v0 = me0.vertices[id0].co
                v1 = me0.vertices[id1].co
                v = v0.lerp(v1, (iso_val-w0)/(w1-w0))
                delete_edges.append(e)
                verts.append(v)
                edges_id[str(id0)+"_"+str(id1)] = count
                edges_id[str(id1)+"_"+str(id0)] = count
                count += 1

        splitted_faces = []

        switch = False
        # splitting faces
        for f in faces_mask:
            # create sub-faces slots. Once a new vertex is reached it will
            # change slot, storing the next vertices for a new face.
            build_faces = [[],[]]
            #switch = False
            verts0 = list(me0.polygons[f.index].vertices)
            verts1 = list(verts0)
            verts1.append(verts1.pop(0)) # shift list
            for id0, id1 in zip(verts0, verts1):

                # add first vertex to active slot
                build_faces[switch].append(id0)

                # try to split edge
                try:
                    # check if the edge must be splitted
                    new_vert = edges_id[str(id0)+"_"+str(id1)]
                    # add new vertex
                    build_faces[switch].append(new_vert)
                    # if there is an open face on the other slot
                    if len(build_faces[not switch]) > 0:
                        # store actual face
                        splitted_faces.append(build_faces[switch])
                        # reset actual faces and switch
                        build_faces[switch] = []
                        # change face slot
                    switch = not switch
                    # continue previous face
                    build_faces[switch].append(new_vert)
                except: pass
            if len(build_faces[not switch]) == 2:
                build_faces[not switch].append(id0)
            if len(build_faces[not switch]) > 2:
                splitted_faces.append(build_faces[not switch])
            # add last face
            splitted_faces.append(build_faces[switch])

        # adding new vertices
        _new_vert = bm.verts.new
        for v in verts: _new_vert(v)
        bm.verts.ensure_lookup_table()

        # deleting old edges/faces
        _remove_edge = bm.edges.remove
        bm.edges.ensure_lookup_table()
        remove_edges = []
        for e in delete_edges: _remove_edge(e)

        bm.verts.ensure_lookup_table()
        # adding new faces
        _new_face = bm.faces.new
        missed_faces = []
        for f in splitted_faces:
            try:
                face_verts = [bm.verts[i] for i in f]
                _new_face(face_verts)
            except:
                missed_faces.append(f)

        # Mask geometry
        if(True):
            _remove_vert = bm.verts.remove
            all_weight = weight + [iso_val+0.0001]*len(verts)
            weight = []
            for w, v in zip(all_weight, bm.verts):
                if w < iso_val: _remove_vert(v)
                else: weight.append(w)

        # Create mesh and object
        name = ob0.name + '_ContourMask_{:.3f}'.format(iso_val)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)

        # Link object to scene and make active
        scn = context.scene
        context.collection.objects.link(ob)
        context.view_layer.objects.active = ob
        ob.select_set(True)
        ob0.select_set(False)

        # generate new vertex group
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)

        if iso_val != 1: mult = 1/(1-iso_val)
        else: mult = 1
        for id in range(len(weight)):
            if self.normalize_weight: w = (weight[id]-iso_val)*mult
            else: w = weight[id]
            ob.vertex_groups[vertex_group_name].add([id], w, 'REPLACE')
        ob.vertex_groups.active_index = group_id

        # align new object
        ob.matrix_world = ob0.matrix_world

        # Add Solidify
        if self.bool_solidify and True:
            ob.modifiers.new(type='SOLIDIFY', name='Solidify')
            ob.modifiers['Solidify'].thickness = 0.05
            ob.modifiers['Solidify'].offset = 0
            ob.modifiers['Solidify'].vertex_group = vertex_group_name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        print("Contour Mask time: " + str(timeit.default_timer() - start_time) + " sec")

        bpy.data.meshes.remove(me0)

        return {'FINISHED'}


class weight_contour_mask_wip(Operator):
    bl_idname = "object.weight_contour_mask"
    bl_label = "Contour Mask"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")
    iso : FloatProperty(
        name="Iso Value", default=0.5, soft_min=0, soft_max=1,
        description="Threshold value")
    bool_solidify : BoolProperty(
        name="Solidify", default=True, description="Add Solidify Modifier")
    normalize_weight : BoolProperty(
        name="Normalize Weight", default=True,
        description="Normalize weight of remaining vertices")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}

        ob0 = bpy.context.object

        iso_val = self.iso
        group_id = ob0.vertex_groups.active_index
        vertex_group_name = ob0.vertex_groups[group_id].name

        #bpy.ops.object.mode_set(mode='EDIT')
        #bpy.ops.mesh.select_all(action='SELECT')
        #bpy.ops.object.mode_set(mode='OBJECT')
        if self.use_modifiers:
            me0 = simple_to_mesh(ob0)#ob0.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
        else:
            me0 = ob0.data.copy()

        # generate new bmesh
        bm = bmesh.new()
        bm.from_mesh(me0)

        # store weight values
        weight = []
        ob = bpy.data.objects.new("temp", me0)
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)
        weight = get_weight_numpy(ob.vertex_groups[vertex_group_name], len(me0.vertices))

        me0, bm, weight = contour_bmesh(me0, bm, weight, iso_val)

        # Mask geometry
        mask = weight >= iso_val
        weight = weight[mask]
        mask = np.logical_not(mask)
        delete_verts = np.array(bm.verts)[mask]
        #for v in delete_verts: bm.verts.remove(v)

        # Create mesh and object
        name = ob0.name + '_ContourMask_{:.3f}'.format(iso_val)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)

        # Link object to scene and make active
        scn = context.scene
        context.collection.objects.link(ob)
        context.view_layer.objects.active = ob
        ob.select_set(True)
        ob0.select_set(False)

        # generate new vertex group
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)

        if iso_val != 1: mult = 1/(1-iso_val)
        else: mult = 1
        for id in range(len(weight)):
            if self.normalize_weight: w = (weight[id]-iso_val)*mult
            else: w = weight[id]
            ob.vertex_groups[vertex_group_name].add([id], w, 'REPLACE')
        ob.vertex_groups.active_index = group_id

        # align new object
        ob.matrix_world = ob0.matrix_world

        # Add Solidify
        if self.bool_solidify and True:
            ob.modifiers.new(type='SOLIDIFY', name='Solidify')
            ob.modifiers['Solidify'].thickness = 0.05
            ob.modifiers['Solidify'].offset = 0
            ob.modifiers['Solidify'].vertex_group = vertex_group_name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        print("Contour Mask time: " + str(timeit.default_timer() - start_time) + " sec")

        bpy.data.meshes.remove(me0)

        return {'FINISHED'}


class weight_contour_curves(Operator):
    bl_idname = "object.weight_contour_curves"
    bl_label = "Contour Curves"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")

    min_iso : FloatProperty(
        name="Min Value", default=0., soft_min=0, soft_max=1,
        description="Minimum weight value")
    max_iso : FloatProperty(
        name="Max Value", default=1, soft_min=0, soft_max=1,
        description="Maximum weight value")
    n_curves : IntProperty(
        name="Curves", default=3, soft_min=1, soft_max=10,
        description="Number of Contour Curves")

    min_rad : FloatProperty(
        name="Min Radius", default=1, soft_min=0, soft_max=1,
        description="Change radius according to Iso Value")
    max_rad : FloatProperty(
        name="Max Radius", default=1, soft_min=0, soft_max=1,
        description="Change radius according to Iso Value")

    @classmethod
    def poll(cls, context):
        ob = context.object
        return len(ob.vertex_groups) > 0 or ob.type == 'CURVE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}
        ob0 = context.object

        group_id = ob0.vertex_groups.active_index
        vertex_group_name = ob0.vertex_groups[group_id].name

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        if self.use_modifiers:
            me0 = simple_to_mesh(ob0) #ob0.to_mesh(preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get()).copy()
        else:
            me0 = ob0.data.copy()

        # generate new bmesh
        bm = bmesh.new()
        bm.from_mesh(me0)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # store weight values
        weight = []
        ob = bpy.data.objects.new("temp", me0)
        for g in ob0.vertex_groups:
            ob.vertex_groups.new(name=g.name)
        weight = get_weight_numpy(ob.vertex_groups[vertex_group_name], len(bm.verts))

        #filtered_edges = bm.edges
        total_verts = np.zeros((0,3))
        total_segments = []
        radius = []

        # start iterate contours levels
        vertices = get_vertices_numpy(me0)
        filtered_edges = get_edges_id_numpy(me0)

        faces_weight = [np.array([weight[v] for v in p.vertices]) for p in me0.polygons]
        fw_min = np.array([np.min(fw) for fw in faces_weight])
        fw_max = np.array([np.max(fw) for fw in faces_weight])

        bm_faces = np.array(bm.faces)

        for c in range(self.n_curves):
            min_iso = min(self.min_iso, self.max_iso)
            max_iso = max(self.min_iso, self.max_iso)
            try:
                iso_val = c*(max_iso-min_iso)/(self.n_curves-1)+min_iso
                if iso_val < 0: iso_val = (min_iso + max_iso)/2
            except:
                iso_val = (min_iso + max_iso)/2

            # remove passed faces
            bool_mask = iso_val < fw_max
            bm_faces = bm_faces[bool_mask]
            fw_min = fw_min[bool_mask]
            fw_max = fw_max[bool_mask]

            # mask faces
            bool_mask = fw_min < iso_val
            faces_mask = bm_faces[bool_mask]

            n_verts = len(bm.verts)
            count = len(total_verts)

            # vertices indexes
            id0 = filtered_edges[:,0]
            id1 = filtered_edges[:,1]
            # vertices weight
            w0 = weight[id0]
            w1 = weight[id1]
            # weight condition
            bool_w0 = w0 < iso_val
            bool_w1 = w1 < iso_val

            # mask all edges that have one weight value below the iso value
            mask_new_verts = np.logical_xor(bool_w0, bool_w1)

            id0 = id0[mask_new_verts]
            id1 = id1[mask_new_verts]
            # filter arrays
            v0 = vertices[id0]
            v1 = vertices[id1]
            w0 = w0[mask_new_verts]
            w1 = w1[mask_new_verts]
            div = (w1-w0)
            if div == 0: div = 0.000001
            param = np.expand_dims((iso_val-w0)/div,axis=1)
            verts = v0 + (v1-v0)*param

            # indexes of edges with new vertices
            edges_index = filtered_edges[mask_new_verts][:,2]
            edges_id = {}
            for i, id in enumerate(edges_index): edges_id[id] = i+len(total_verts)

            # remove all edges completely below the iso value
            mask_edges = np.logical_not(np.logical_and(bool_w0, bool_w1))
            filtered_edges = filtered_edges[mask_edges]
            if len(verts) == 0: continue

            # finding segments
            segments = []
            for f in faces_mask:
                seg = []
                for e in f.edges:
                    try:
                        seg.append(edges_id[e.index])
                        if len(seg) == 2:
                            segments.append(seg)
                            seg = []
                    except: pass


            #curves_points_indexes = find_curves(segments)
            total_segments = total_segments + segments
            total_verts = np.concatenate((total_verts,verts))

            if self.min_rad != self.max_rad:
                try:
                    iso_rad = c*(self.max_rad-self.min_rad)/(self.n_curves-1)+self.min_rad
                    if iso_rad < 0: iso_rad = (self.min_rad + self.max_rad)/2
                except:
                    iso_rad = (self.min_rad + self.max_rad)/2
                radius = radius + [iso_rad]*len(verts)
        print("Contour Curves, computing time: " + str(timeit.default_timer() - start_time) + " sec")
        bm.free()
        bm = bmesh.new()
        # adding new vertices  _local for fast access
        _new_vert = bm.verts.new
        for v in total_verts: _new_vert(v)
        bm.verts.ensure_lookup_table()

        # adding new edges
        _new_edge = bm.edges.new
        for s in total_segments:
            try:
                pts = [bm.verts[i] for i in s]
                _new_edge(pts)
            except: pass


        try:
            name = ob0.name + '_ContourCurves'
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            bm.free()
            ob = bpy.data.objects.new(name, me)
            # Link object to scene and make active
            scn = context.scene
            context.collection.objects.link(ob)
            context.view_layer.objects.active = ob
            ob.select_set(True)
            ob0.select_set(False)

            print("Contour Curves, bmesh time: " + str(timeit.default_timer() - start_time) + " sec")
            bpy.ops.object.convert(target='CURVE')
            ob = context.object
            if not (self.min_rad == 0 and self.max_rad == 0):
                if self.min_rad != self.max_rad:
                    count = 0
                    for s in ob.data.splines:
                        for p in s.points:
                            p.radius = radius[count]
                            count += 1
                else:
                    for s in ob.data.splines:
                        for p in s.points:
                            p.radius = self.min_rad
            ob.data.bevel_depth = 0.01
            ob.data.fill_mode = 'FULL'
            ob.data.bevel_resolution = 3
        except:
            self.report({'ERROR'}, "There are no values in the chosen range")
            return {'CANCELLED'}

        # align new object
        ob.matrix_world = ob0.matrix_world
        print("Contour Curves time: " + str(timeit.default_timer() - start_time) + " sec")

        bpy.data.meshes.remove(me0)
        bpy.data.meshes.remove(me)

        return {'FINISHED'}

class tissue_weight_contour_curves_pattern(Operator):
    bl_idname = "object.tissue_weight_contour_curves_pattern"
    bl_label = "Contour Curves"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")

    auto_bevel : BoolProperty(
        name="Automatic Bevel", default=False,
        description="Bevel depends on weight density")

    min_iso : FloatProperty(
        name="Min Value", default=0., soft_min=0, soft_max=1,
        description="Minimum weight value")
    max_iso : FloatProperty(
        name="Max Value", default=1, soft_min=0, soft_max=1,
        description="Maximum weight value")
    n_curves : IntProperty(
        name="Curves", default=10, soft_min=1, soft_max=100,
        description="Number of Contour Curves")
    min_rad = 1
    max_rad = 1

    in_displace : FloatProperty(
        name="Displace A", default=0, soft_min=-10, soft_max=10,
        description="Pattern displace strength")
    out_displace : FloatProperty(
        name="Displace B", default=2, soft_min=-10, soft_max=10,
        description="Pattern displace strength")

    in_steps : IntProperty(
        name="Steps A", default=1, min=0, soft_max=10,
        description="Number of layers to move inwards")
    out_steps : IntProperty(
        name="Steps B", default=1, min=0, soft_max=10,
        description="Number of layers to move outwards")
    limit_z : BoolProperty(
        name="Limit Z", default=False,
        description="Limit Pattern in Z")

    merge : BoolProperty(
        name="Merge Vertices", default=True,
        description="Merge points")
    merge_thres : FloatProperty(
        name="Merge Threshold", default=0.01, min=0, soft_max=1,
        description="Minimum Curve Radius")

    bevel_depth : FloatProperty(
        name="Bevel Depth", default=0, min=0, soft_max=1,
        description="")
    min_bevel_depth : FloatProperty(
        name="Min Bevel Depth", default=0.1, min=0, soft_max=1,
        description="")
    max_bevel_depth : FloatProperty(
        name="Max Bevel Depth", default=1, min=0, soft_max=1,
        description="")
    remove_open_curves : BoolProperty(
        name="Remove Open Curves", default=False,
        description="Remove Open Curves")

    vertex_group_pattern : StringProperty(
        name="Displace", default='',
        description="Vertex Group used for pattern displace")

    vertex_group_bevel : StringProperty(
        name="Bevel", default='',
        description="Variable Bevel depth")

    object_name : StringProperty(
        name="Active Object", default='',
        description="")

    try: vg_name = bpy.context.object.vertex_groups.active.name
    except: vg_name = ''

    vertex_group_contour : StringProperty(
        name="Contour", default=vg_name,
        description="Vertex Group used for contouring")
    clean_distance : FloatProperty(
        name="Clean Distance", default=0, min=0, soft_max=10,
        description="Remove short segments")


    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and len(ob.vertex_groups) > 0 or ob.type == 'CURVE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        if not context.object.type == 'CURVE':
            self.object_name = context.object.name
        ob = bpy.data.objects[self.object_name]
        if self.vertex_group_contour not in [vg.name for vg in ob.vertex_groups]:
            self.vertex_group_contour = ob.vertex_groups.active.name
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "use_modifiers")
        col.label(text="Contour Curves:")
        col.prop_search(self, 'vertex_group_contour', ob, "vertex_groups", text='')
        row = col.row(align=True)
        row.prop(self,'min_iso')
        row.prop(self,'max_iso')
        col.prop(self,'n_curves')
        col.separator()
        col.label(text='Curves Bevel:')
        col.prop(self,'auto_bevel')
        if not self.auto_bevel:
            col.prop_search(self, 'vertex_group_bevel', ob, "vertex_groups", text='')
        if self.vertex_group_bevel != '' or self.auto_bevel:
            row = col.row(align=True)
            row.prop(self,'min_bevel_depth')
            row.prop(self,'max_bevel_depth')
        else:
            col.prop(self,'bevel_depth')
        col.separator()

        col.label(text="Displace Pattern:")
        col.prop_search(self, 'vertex_group_pattern', ob, "vertex_groups", text='')
        if self.vertex_group_pattern != '':
            row = col.row(align=True)
            row.prop(self,'in_steps')
            row.prop(self,'out_steps')
            row = col.row(align=True)
            row.prop(self,'in_displace')
            row.prop(self,'out_displace')
            col.prop(self,'limit_z')
        col.separator()

        col.label(text='Clean Curves:')
        col.prop(self,'clean_distance')
        col.prop(self,'remove_open_curves')

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}
        ob0 = bpy.data.objects[self.object_name]

        dg = context.evaluated_depsgraph_get()
        ob = ob0.evaluated_get(dg)
        me0 = ob.data

        # generate new bmesh
        bm = bmesh.new()
        bm.from_mesh(me0)
        n_verts = len(bm.verts)

        # store weight values
        try:
            weight = get_weight_numpy(ob.vertex_groups[self.vertex_group_contour], len(me0.vertices))
        except:
            bm.free()
            self.report({'ERROR'}, "Please select a Vertex Group for contouring")
            return {'CANCELLED'}

        try:
            pattern_weight = get_weight_numpy(ob.vertex_groups[self.vertex_group_pattern], len(me0.vertices))
        except:
            #self.report({'WARNING'}, "There is no Vertex Group assigned to the pattern displace")
            pattern_weight = np.zeros(len(me0.vertices))

        variable_bevel = False
        try:
            bevel_weight = get_weight_numpy(ob.vertex_groups[self.vertex_group_bevel], len(me0.vertices))
            variable_bevel = True
        except:
            bevel_weight = np.ones(len(me0.vertices))

        if self.auto_bevel:
            # calc weight density
            bevel_weight = np.ones(len(me0.vertices))*10000
            bevel_weight = np.zeros(len(me0.vertices))
            edges_length = np.array([e.calc_length() for e in bm.edges])
            edges_dw = np.array([max(abs(weight[e.verts[0].index]-weight[e.verts[1].index]),0.000001) for e in bm.edges])
            dens = edges_length/edges_dw
            n_records = np.zeros(len(me0.vertices))
            for i, e in enumerate(bm.edges):
                for v in e.verts:
                    id = v.index
                    #bevel_weight[id] = min(bevel_weight[id], dens[i])
                    bevel_weight[id] += dens[i]
                    n_records[id] += 1
            bevel_weight = bevel_weight/n_records
            bevel_weight = (bevel_weight - min(bevel_weight))/(max(bevel_weight) - min(bevel_weight))
            #bevel_weight = 1-bevel_weight
            variable_bevel = True

        #filtered_edges = bm.edges
        total_verts = np.zeros((0,3))
        total_radii = np.zeros((0,1))
        total_segments = []# np.array([])
        radius = []

        # start iterate contours levels
        vertices, normals = get_vertices_and_normals_numpy(me0)
        filtered_edges = get_edges_id_numpy(me0)

        faces_weight = [np.array([weight[v] for v in p.vertices]) for p in me0.polygons]
        fw_min = np.array([np.min(fw) for fw in faces_weight])
        fw_max = np.array([np.max(fw) for fw in faces_weight])

        bm_faces = np.array(bm.faces)

        #print("Contour Curves, data loaded: " + str(timeit.default_timer() - start_time) + " sec")
        step_time = timeit.default_timer()
        for c in range(self.n_curves):
            min_iso = min(self.min_iso, self.max_iso)
            max_iso = max(self.min_iso, self.max_iso)
            try:
                iso_val = c*(max_iso-min_iso)/(self.n_curves-1)+min_iso
                if iso_val < 0: iso_val = (min_iso + max_iso)/2
            except:
                iso_val = (min_iso + max_iso)/2

            #if c == 0 and self.auto_bevel:


            # remove passed faces
            bool_mask = iso_val < fw_max
            bm_faces = bm_faces[bool_mask]
            fw_min = fw_min[bool_mask]
            fw_max = fw_max[bool_mask]

            # mask faces
            bool_mask = fw_min < iso_val
            faces_mask = bm_faces[bool_mask]

            count = len(total_verts)

            new_filtered_edges, edges_index, verts, bevel = contour_edges_pattern(self, c, len(total_verts), iso_val, vertices, normals, filtered_edges, weight, pattern_weight, bevel_weight)

            if len(edges_index) > 0:
                if self.auto_bevel and False:
                    bevel = 1-dens[edges_index]
                    bevel = bevel[:,np.newaxis]
                if self.max_bevel_depth != self.min_bevel_depth:
                    min_radius = self.min_bevel_depth / max(0.0001,self.max_bevel_depth)
                    radii = min_radius + bevel*(1 - min_radius)
                else:
                    radii = bevel
            else:
                continue

            if verts[0,0] == None: continue
            else: filtered_edges = new_filtered_edges
            edges_id = {}
            for i, id in enumerate(edges_index): edges_id[id] = i + count

            if len(verts) == 0: continue

            # finding segments
            segments = []
            for f in faces_mask:
                seg = []
                for e in f.edges:
                    try:
                        #seg.append(new_ids[np.where(edges_index == e.index)[0][0]])
                        seg.append(edges_id[e.index])
                        if len(seg) == 2:
                            segments.append(seg)
                            seg = []
                    except: pass

            total_segments = total_segments + segments
            total_verts = np.concatenate((total_verts, verts))
            total_radii = np.concatenate((total_radii, radii))

            if self.min_rad != self.max_rad:
                try:
                    iso_rad = c*(self.max_rad-self.min_rad)/(self.n_curves-1)+self.min_rad
                    if iso_rad < 0: iso_rad = (self.min_rad + self.max_rad)/2
                except:
                    iso_rad = (self.min_rad + self.max_rad)/2
                radius = radius + [iso_rad]*len(verts)
        #print("Contour Curves, points computing: " + str(timeit.default_timer() - step_time) + " sec")
        step_time = timeit.default_timer()

        if len(total_segments) > 0:
            step_time = timeit.default_timer()
            ordered_points = find_curves(total_segments, len(total_verts))
            #print("Contour Curves, point ordered in: " + str(timeit.default_timer() - step_time) + " sec")
            step_time = timeit.default_timer()
            crv = curve_from_pydata(total_verts, total_radii, ordered_points, ob0.name + '_ContourCurves', self.remove_open_curves, merge_distance=self.clean_distance)
            context.view_layer.objects.active = crv
            if variable_bevel: crv.data.bevel_depth = self.max_bevel_depth
            else: crv.data.bevel_depth = self.bevel_depth

            crv.select_set(True)
            ob0.select_set(False)
            crv.matrix_world = ob0.matrix_world
            #print("Contour Curves, curves created in: " + str(timeit.default_timer() - step_time) + " sec")
        else:
            bm.free()
            self.report({'ERROR'}, "There are no values in the chosen range")
            return {'CANCELLED'}
        bm.free()
        print("Contour Curves, total time: " + str(timeit.default_timer() - start_time) + " sec")
        return {'FINISHED'}

class vertex_colors_to_vertex_groups(Operator):
    bl_idname = "object.vertex_colors_to_vertex_groups"
    bl_label = "Vertex Color"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Convert the active Vertex Color into a Vertex Group.")

    red : BoolProperty(
        name="red channel", default=False, description="convert red channel")
    green : BoolProperty(
        name="green channel", default=False,
        description="convert green channel")
    blue : BoolProperty(
        name="blue channel", default=False, description="convert blue channel")
    value : BoolProperty(
        name="value channel", default=True, description="convert value channel")
    invert : BoolProperty(
         name="invert", default=False, description="invert all color channels")

    @classmethod
    def poll(cls, context):
        try:
            return len(context.object.data.vertex_colors) > 0
        except: return False

    def execute(self, context):
        obj = context.active_object
        id = len(obj.vertex_groups)
        id_red = id
        id_green = id
        id_blue = id
        id_value = id

        boolCol = len(obj.data.vertex_colors)
        if(boolCol): col_name = obj.data.vertex_colors.active.name
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        if(self.red and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_red = id
            obj.vertex_groups[id_red].name = col_name + '_red'
            id+=1
        if(self.green and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_green = id
            obj.vertex_groups[id_green].name = col_name + '_green'
            id+=1
        if(self.blue and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_blue = id
            obj.vertex_groups[id_blue].name = col_name + '_blue'
            id+=1
        if(self.value and boolCol):
            bpy.ops.object.vertex_group_add()
            bpy.ops.object.vertex_group_assign()
            id_value = id
            obj.vertex_groups[id_value].name = col_name + '_value'
            id+=1

        mult = 1
        if(self.invert): mult = -1
        bpy.ops.object.mode_set(mode='OBJECT')
        sub_red = 1 + self.value + self.blue + self.green
        sub_green = 1 + self.value + self.blue
        sub_blue = 1 + self.value
        sub_value = 1

        id = len(obj.vertex_groups)
        if(id_red <= id and id_green <= id and id_blue <= id and id_value <= \
                id and boolCol):
            v_colors = obj.data.vertex_colors.active.data
            i = 0
            for f in obj.data.polygons:
                for v in f.vertices:
                    gr = obj.data.vertices[v].groups
                    if(self.red): gr[min(len(gr)-sub_red, id_red)].weight = \
                        self.invert + mult * v_colors[i].color[0]
                    if(self.green): gr[min(len(gr)-sub_green, id_green)].weight\
                        = self.invert + mult * v_colors[i].color[1]
                    if(self.blue): gr[min(len(gr)-sub_blue, id_blue)].weight = \
                        self.invert + mult * v_colors[i].color[2]
                    if(self.value):
                        r = v_colors[i].color[0]
                        g = v_colors[i].color[1]
                        b = v_colors[i].color[2]
                        gr[min(len(gr)-sub_value, id_value)].weight\
                        = self.invert + mult * (0.2126*r + 0.7152*g + 0.0722*b)
                    i+=1
            bpy.ops.paint.weight_paint_toggle()
        return {'FINISHED'}

class vertex_group_to_vertex_colors(Operator):
    bl_idname = "object.vertex_group_to_vertex_colors"
    bl_label = "Vertex Group"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Convert the active Vertex Group into a Vertex Color.")

    channel : EnumProperty(
        items=[('BLUE', 'Blue Channel', 'Convert to Blue Channel'),
               ('GREEN', 'Green Channel', 'Convert to Green Channel'),
               ('RED', 'Red Channel', 'Convert to Red Channel'),
               ('VALUE', 'Value Channel', 'Convert to Grayscale'),
               ('FALSE_COLORS', 'False Colors', 'Convert to False Colors')],
        name="Convert to", description="Choose how to convert vertex group",
        default="VALUE", options={'LIBRARY_EDITABLE'})

    invert : BoolProperty(
        name="invert", default=False, description="invert color channel")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        obj = context.active_object
        group_id = obj.vertex_groups.active_index
        if (group_id == -1):
            return {'FINISHED'}

        bpy.ops.object.mode_set(mode='OBJECT')
        group_name = obj.vertex_groups[group_id].name
        bpy.ops.mesh.vertex_color_add()
        colors_id = obj.data.vertex_colors.active_index

        colors_name = group_name
        if(self.channel == 'FALSE_COLORS'): colors_name += "_false_colors"
        elif(self.channel == 'VALUE'):  colors_name += "_value"
        elif(self.channel == 'RED'):  colors_name += "_red"
        elif(self.channel == 'GREEN'):  colors_name += "_green"
        elif(self.channel == 'BLUE'):  colors_name += "_blue"
        context.object.data.vertex_colors[colors_id].name = colors_name

        v_colors = obj.data.vertex_colors.active.data

        mult = 1
        if(self.invert): mult = -1

        i = 0
        for f in obj.data.polygons:
            for v in f.vertices:
                gr = obj.data.vertices[v].groups

                if(self.channel == 'FALSE_COLORS'): v_colors[i].color = (0,0,0.5,1)
                else: v_colors[i].color = (0,0,0,1)

                for g in gr:
                    if g.group == group_id:
                        w = g.weight
                        if(self.channel == 'FALSE_COLORS'):
                            mult = 0.6+0.4*w
                            if w < 0.25:
                                v_colors[i].color = (0, w*4*mult, 1*mult,1)
                            elif w < 0.5:
                                v_colors[i].color = (0, 1*mult, (1-(w-0.25)*4)*mult,1)
                            elif w < 0.75:
                                v_colors[i].color = ((w-0.5)*4*mult,1*mult,0,1)
                            else:
                                v_colors[i].color = (1*mult,(1-(w-0.75)*4)*mult,0,1)
                        elif(self.channel == 'VALUE'):
                            v_colors[i].color = (
                                self.invert + mult * w,
                                self.invert + mult * w,
                                self.invert + mult * w,
                                1)
                        elif(self.channel == 'RED'):
                            v_colors[i].color = (
                                self.invert + mult * w,0,0,1)
                        elif(self.channel == 'GREEN'):
                            v_colors[i].color = (
                                0, self.invert + mult * w,0,1)
                        elif(self.channel == 'BLUE'):
                            v_colors[i].color = (
                                0,0, self.invert + mult * w,1)
                i+=1
        bpy.ops.paint.vertex_paint_toggle()
        context.object.data.vertex_colors[colors_id].active_render = True
        return {'FINISHED'}

class curvature_to_vertex_groups(Operator):
    bl_idname = "object.curvature_to_vertex_groups"
    bl_label = "Curvature"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Generate a Vertex Group based on the curvature of the"
                      "mesh. Is based on Dirty Vertex Color.")

    invert : BoolProperty(
        name="invert", default=False, description="invert values")

    blur_strength : FloatProperty(
      name="Blur Strength", default=1, min=0.001,
      max=1, description="Blur strength per iteration")

    blur_iterations : IntProperty(
      name="Blur Iterations", default=1, min=0,
      max=40, description="Number of times to blur the values")

    min_angle : FloatProperty(
      name="Min Angle", default=0, min=0,
      max=pi/2, subtype='ANGLE', description="Minimum angle")

    max_angle : FloatProperty(
      name="Max Angle", default=pi, min=pi/2,
      max=pi, subtype='ANGLE', description="Maximum angle")

    invert : BoolProperty(
        name="Invert", default=False,
        description="Invert the curvature map")

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.mesh.vertex_color_add()
        vertex_colors = context.active_object.data.vertex_colors
        vertex_colors[-1].active = True
        vertex_colors[-1].active_render = True
        vertex_colors[-1].name = "Curvature"
        for c in vertex_colors[-1].data: c.color = (1,1,1,1)
        bpy.ops.object.mode_set(mode='VERTEX_PAINT')
        bpy.ops.paint.vertex_color_dirt(
            blur_strength=self.blur_strength,
            blur_iterations=self.blur_iterations, clean_angle=self.max_angle,
            dirt_angle=self.min_angle)
        bpy.ops.object.vertex_colors_to_vertex_groups(invert=self.invert)
        bpy.ops.mesh.vertex_color_remove()
        return {'FINISHED'}


class face_area_to_vertex_groups(Operator):
    bl_idname = "object.face_area_to_vertex_groups"
    bl_label = "Area"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Generate a Vertex Group based on the area of individual"
                      "faces.")

    invert : BoolProperty(
        name="invert", default=False, description="invert values")
    bounds : EnumProperty(
        items=(('MANUAL', "Manual Bounds", ""),
            ('AUTOMATIC', "Automatic Bounds", "")),
        default='AUTOMATIC', name="Bounds")

    min_area : FloatProperty(
        name="Min", default=0.01, soft_min=0, soft_max=1,
        description="Faces with 0 weight")

    max_area : FloatProperty(
        name="Max", default=0.1, soft_min=0, soft_max=1,
        description="Faces with 1 weight")

    def draw(self, context):
        layout = self.layout
        layout.label(text="Bounds")
        layout.prop(self, "bounds", text="")
        if self.bounds == 'MANUAL':
            layout.prop(self, "min_area")
            layout.prop(self, "max_area")

    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}
        ob.vertex_groups.new(name="Faces Area")

        areas = [[] for v in ob.data.vertices]

        for p in ob.data.polygons:
            for v in p.vertices:
                areas[v].append(p.area)

        for i in range(len(areas)):
            areas[i] = mean(areas[i])
        if self.bounds == 'MANUAL':
            min_area = self.min_area
            max_area = self.max_area
        elif self.bounds == 'AUTOMATIC':
            min_area = min(areas)
            max_area = max(areas)
        elif self.bounds == 'COMPRESSION':
            min_area = 1
            max_area = min(areas)
        elif self.bounds == 'TENSION':
            min_area = 1
            max_area = max(areas)
        delta_area = max_area - min_area
        if delta_area == 0:
            delta_area = 0.0001
            if self.bounds == 'MANUAL':
                delta_area = 0.0001
            else:
                self.report({'ERROR'}, "The faces have the same areas")
                #return {'CANCELLED'}
        for i in range(len(areas)):
            weight = (areas[i] - min_area)/delta_area
            ob.vertex_groups[-1].add([i], weight, 'REPLACE')
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}

class random_weight(Operator):
    bl_idname = "object.random_weight"
    bl_label = "Random"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Generate a random Vertex Group")

    min_val : FloatProperty(
        name="Min", default=0, soft_min=0, soft_max=1,
        description="Minimum Value")

    max_val : FloatProperty(
        name="Max", default=1, soft_min=0, soft_max=1,
        description="Maximum Value")

    #def draw(self, context):
    #    layout = self.layout
    #    layout.prop(self, "min_area")
    #    layout.prop(self, "max_area")
    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        try: ob = context.object
        except:
            self.report({'ERROR'}, "Please select an Object")
            return {'CANCELLED'}
        #ob.vertex_groups.new(name="Random")
        n_verts = len(ob.data.vertices)
        weight = np.random.uniform(low=self.min_val, high=self.max_val, size=(n_verts,))
        np.clip(weight, 0, 1, out=weight)

        group_id = ob.vertex_groups.active_index
        for i in range(n_verts):
            ob.vertex_groups[group_id].add([i], weight[i], 'REPLACE')
        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}


class harmonic_weight(Operator):
    bl_idname = "object.harmonic_weight"
    bl_label = "Harmonic"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Create an harmonic variation of the active Vertex Group")

    freq : FloatProperty(
        name="Frequency", default=20, soft_min=0,
        soft_max=100, description="Wave frequency")

    amp : FloatProperty(
        name="Amplitude", default=1, soft_min=0,
        soft_max=10, description="Wave amplitude")

    midlevel : FloatProperty(
        name="Midlevel", default=0, min=-1,
        max=1, description="Midlevel")

    add : FloatProperty(
        name="Add", default=0, min=-1,
        max=1, description="Add to the Weight")

    mult : FloatProperty(
        name="Multiply", default=0, min=0,
        max=1, description="Multiply for he Weight")

    @classmethod
    def poll(cls, context):
        return len(context.object.vertex_groups) > 0

    def execute(self, context):
        ob = context.active_object
        if len(ob.vertex_groups) > 0:
            group_id = ob.vertex_groups.active_index
            ob.vertex_groups.new(name="Harmonic")
            for i in range(len(ob.data.vertices)):
                try: val = ob.vertex_groups[group_id].weight(i)
                except: val = 0
                weight = self.amp*(math.sin(val*self.freq) - self.midlevel)/2 + 0.5 + self.add*val*(1-(1-val)*self.mult)
                ob.vertex_groups[-1].add([i], weight, 'REPLACE')
            ob.data.update()
        else:
            self.report({'ERROR'}, "Active object doesn't have vertex groups")
            return {'CANCELLED'}
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        return {'FINISHED'}


class tissue_weight_distance(Operator):
    bl_idname = "object.tissue_weight_distance"
    bl_label = "Weight Distance"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ("Create a weight map according to the distance from the "
                    "selected vertices along the mesh surface")

    def fill_neighbors(self,verts,weight):
        neigh = {}
        for v0 in verts:
            for f in v0.link_faces:
                for v1 in f.verts:
                    dist = weight[v0.index] + (v0.co-v1.co).length
                    w1 = weight[v1.index]
                    if w1 == None or w1 > dist:
                        weight[v1.index] = dist
                        neigh[v1] = 0
        if len(neigh) == 0: return weight
        else: return self.fill_neighbors(neigh.keys(), weight)

    def execute(self, context):
        ob = context.object
        old_mode = ob.mode
        if old_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        me = ob.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # store weight values
        weight = [None]*len(bm.verts)

        selected = [v for v in bm.verts if v.select]
        if len(selected) == 0:
            bpy.ops.object.mode_set(mode=old_mode)
            message = "Please, select one or more vertices"
            self.report({'ERROR'}, message)
            return {'CANCELLED'}
        for v in selected: weight[v.index] = 0
        weight = self.fill_neighbors(selected, weight)

        for i in range(len(weight)):
            if weight[i] == None: weight[i] = 0
        weight = np.array(weight)
        max_dist = np.max(weight)
        if max_dist > 0:
            weight /= max_dist

        vg = ob.vertex_groups.new(name='Distance: {:.4f}'.format(max_dist))
        for i, w in enumerate(weight):
            vg.add([i], w, 'REPLACE')
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
        bm.free()
        return {'FINISHED'}



class TISSUE_PT_color(Panel):
    bl_label = "Tissue Tools"
    bl_category = "Tissue"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    #bl_options = {'DEFAULT_CLOSED'}
    bl_context = "vertexpaint"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("object.vertex_colors_to_vertex_groups",
            icon="GROUP_VERTEX", text="Convert to Weight")

class TISSUE_PT_weight(Panel):
    bl_label = "Tissue Tools"
    bl_category = "Tissue"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    #bl_options = {'DEFAULT_CLOSED'}
    bl_context = "weightpaint"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        #if context.object.type == 'MESH' and context.mode == 'OBJECT':
            #col.label(text="Transform:")
            #col.separator()
        #elif bpy.context.mode == 'PAINT_WEIGHT':
        col.label(text="Weight Generate:")
        #col.operator(
        #    "object.vertex_colors_to_vertex_groups", icon="GROUP_VCOL")
        col.operator("object.face_area_to_vertex_groups", icon="FACESEL")
        col.operator("object.curvature_to_vertex_groups", icon="SMOOTHCURVE")
        col.operator("object.tissue_weight_distance", icon="TRACKING")
        row = col.row(align=True)
        try: row.operator("object.weight_formula", icon="CON_TRANSFORM")
        except: row.operator("object.weight_formula")#, icon="CON_TRANSFORM")
        row.operator("object.update_weight_formula", icon="FILE_REFRESH", text='')#, icon="CON_TRANSFORM")
        #col.label(text="Weight Processing:")
        col.separator()

        # TO BE FIXED
        col.operator("object.weight_laplacian", icon="SMOOTHCURVE")

        col.label(text="Weight Edit:")
        col.operator("object.harmonic_weight", icon="IPO_ELASTIC")
        col.operator("object.vertex_group_to_vertex_colors", icon="GROUP_VCOL",
            text="Convert to Colors")
        col.operator("object.random_weight", icon="RNDCURVE")
        col.separator()
        col.label(text="Deformation Analysis:")
        col.operator("object.edges_deformation", icon="DRIVER_DISTANCE")#FULLSCREEN_ENTER")
        col.operator("object.edges_bending", icon="DRIVER_ROTATIONAL_DIFFERENCE")#"MOD_SIMPLEDEFORM")
        col.separator()
        col.label(text="Weight Curves:")
        #col.operator("object.weight_contour_curves", icon="MOD_CURVE")
        col.operator("object.tissue_weight_streamlines", icon="ANIM")
        col.operator("object.tissue_weight_contour_curves_pattern", icon="FORCE_TURBULENCE")
        col.separator()
        col.operator("object.weight_contour_displace", icon="MOD_DISPLACE")
        col.operator("object.weight_contour_mask", icon="MOD_MASK")
        col.separator()
        col.label(text="Simulations:")
        #col.operator("object.reaction_diffusion", icon="MOD_OCEAN")
        col.operator("object.start_reaction_diffusion",
                    icon="EXPERIMENTAL",
                    text="Reaction-Diffusion")

        col.separator()
        col.label(text="Materials:")
        col.operator("object.random_materials", icon='COLOR')
        col.operator("object.weight_to_materials", icon='GROUP_VERTEX')

        #col.prop(context.object, "reaction_diffusion_run", icon="PLAY", text="Run Simulation")
        ####col.prop(context.object, "reaction_diffusion_run")
        #col.separator()
        #col.label(text="Vertex Color from:")
        #col.operator("object.vertex_group_to_vertex_colors", icon="GROUP_VERTEX")




class start_reaction_diffusion(Operator):
    bl_idname = "object.start_reaction_diffusion"
    bl_label = "Start Reaction Diffusion"
    bl_description = ("Run a Reaction-Diffusion based on existing Vertex Groups: A and B")
    bl_options = {'REGISTER', 'UNDO'}

    run : BoolProperty(
        name="Run Reaction-Diffusion", default=True, description="Compute a new iteration on frame changes")

    time_steps : IntProperty(
        name="Steps", default=10, min=0, soft_max=50,
        description="Number of Steps")

    dt : FloatProperty(
        name="dt", default=1, min=0, soft_max=0.2,
        description="Time Step")

    diff_a : FloatProperty(
        name="Diff A", default=0.18, min=0, soft_max=2,
        description="Diffusion A")

    diff_b : FloatProperty(
        name="Diff B", default=0.09, min=0, soft_max=2,
        description="Diffusion B")

    f : FloatProperty(
        name="f", default=0.055, min=0, soft_min=0.01, soft_max=0.06, max=0.1, precision=4,
        description="Feed Rate")

    k : FloatProperty(
        name="k", default=0.062, min=0, soft_min=0.035, soft_max=0.065, max=0.1, precision=4,
        description="Kill Rate")

    @classmethod
    def poll(cls, context):
        return context.object.type == 'MESH' and context.mode != 'EDIT_MESH'

    def execute(self, context):
        reaction_diffusion_add_handler(self, context)
        set_animatable_fix_handler(self, context)

        ob = context.object

        ob.reaction_diffusion_settings.run = self.run
        ob.reaction_diffusion_settings.dt = self.dt
        ob.reaction_diffusion_settings.time_steps = self.time_steps
        ob.reaction_diffusion_settings.f = self.f
        ob.reaction_diffusion_settings.k = self.k
        ob.reaction_diffusion_settings.diff_a = self.diff_a
        ob.reaction_diffusion_settings.diff_b = self.diff_b


        # check vertex group A
        try:
            vg = ob.vertex_groups['A']
        except:
            ob.vertex_groups.new(name='A')
        # check vertex group B
        try:
            vg = ob.vertex_groups['B']
        except:
            ob.vertex_groups.new(name='B')

        for v in ob.data.vertices:
            ob.vertex_groups['A'].add([v.index], 1, 'REPLACE')
            ob.vertex_groups['B'].add([v.index], 0, 'REPLACE')

        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        return {'FINISHED'}

class reset_reaction_diffusion_weight(Operator):
    bl_idname = "object.reset_reaction_diffusion_weight"
    bl_label = "Reset Reaction Diffusion Weight"
    bl_description = ("Set A and B weight to default values")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.type == 'MESH' and context.mode != 'EDIT_MESH'

    def execute(self, context):
        reaction_diffusion_add_handler(self, context)
        set_animatable_fix_handler(self, context)

        ob = context.object

        # check vertex group A
        try:
            vg = ob.vertex_groups['A']
        except:
            ob.vertex_groups.new(name='A')
        # check vertex group B
        try:
            vg = ob.vertex_groups['B']
        except:
            ob.vertex_groups.new(name='B')

        for v in ob.data.vertices:
            ob.vertex_groups['A'].add([v.index], 1, 'REPLACE')
            ob.vertex_groups['B'].add([v.index], 0, 'REPLACE')

        ob.vertex_groups.update()
        ob.data.update()
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

        return {'FINISHED'}

class bake_reaction_diffusion(Operator):
    bl_idname = "object.bake_reaction_diffusion"
    bl_label = "Bake Data"
    bl_description = ("Bake the Reaction-Diffusion to the cache directory")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.type == 'MESH' and context.mode != 'EDIT_MESH'

    def execute(self, context):
        ob = context.object
        props = ob.reaction_diffusion_settings
        for i in range(props.cache_frame_start, props.cache_frame_end):
            context.scene.frame_current = i
            reaction_diffusion_def(ob, bake=True)
        props.bool_cache = True

        return {'FINISHED'}

class reaction_diffusion_free_data(Operator):
    bl_idname = "object.reaction_diffusion_free_data"
    bl_label = "Free Data"
    bl_description = ("Free Reaction-Diffusion data")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.type == 'MESH'

    def execute(self, context):
        ob = context.object
        props = ob.reaction_diffusion_settings
        props.bool_cache = False

        folder = Path(props.cache_dir)
        for i in range(props.cache_frame_start, props.cache_frame_end):
            data_a = folder / "a_{:04d}".format(i)
            if os.path.exists(data_a):
                os.remove(data_a)
            data_a = folder / "b_{:04d}".format(i)
            if os.path.exists(data_a):
                os.remove(data_a)
        return {'FINISHED'}

from bpy.app.handlers import persistent

def reaction_diffusion_scene(scene, bake=False):
    for ob in scene.objects:
        if ob.reaction_diffusion_settings.run:
            reaction_diffusion_def(ob)

def reaction_diffusion_def(ob, bake=False):
    scene = bpy.context.scene
    start = time.time()
    if type(ob) == bpy.types.Scene: return None
    props = ob.reaction_diffusion_settings

    if bake or props.bool_cache:
        if props.cache_dir == '':
            letters = string.ascii_letters
            random_name = ''.join(rnd.choice(letters) for i in range(6))
            if bpy.context.blend_data.filepath == '':
                folder = Path(bpy.context.preferences.filepaths.temporary_directory)
                folder = folder / 'reaction_diffusion_cache' / random_name
            else:
                folder = '//' + Path(bpy.context.blend_data.filepath).stem
                folder = Path(bpy.path.abspath(folder)) / 'reaction_diffusion_cache' / random_name
            folder.mkdir(parents=True, exist_ok=True)
            props.cache_dir = str(folder)
        else:
            folder = Path(props.cache_dir)

    if props.bool_mod:
        # hide deforming modifiers
        mod_visibility = []
        for m in ob.modifiers:
            mod_visibility.append(m.show_viewport)
            if not mod_preserve_shape(m): m.show_viewport = False

        # evaluated mesh
        dg = bpy.context.evaluated_depsgraph_get()
        ob_eval = ob.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ob_eval, preserve_all_data_layers=True, depsgraph=dg)

        # set original visibility
        for v, m in zip(mod_visibility, ob.modifiers):
            m.show_viewport = v
        ob.modifiers.update()
    else:
        me = ob.data
    bm = bmesh.new()   # create an empty BMesh
    bm.from_mesh(me)   # fill it in from a Mesh
    dvert_lay = bm.verts.layers.deform.active
    n_edges = len(me.edges)
    n_verts = len(me.vertices)
    a = np.zeros(n_verts)
    b = np.zeros(n_verts)
    group_index_a = ob.vertex_groups["A"].index
    group_index_b = ob.vertex_groups["B"].index
    print("{:6d} Reaction-Diffusion: {}".format(scene.frame_current, ob.name))

    if not props.bool_cache:
        dt = props.dt
        time_steps = props.time_steps
        f = props.f
        k = props.k
        diff_a = props.diff_a
        diff_b = props.diff_b
        scale = props.diff_mult

        brush_mult = props.brush_mult

        # store weight values
        if 'dB' in ob.vertex_groups: db = np.zeros(n_verts)
        if 'grad' in ob.vertex_groups: grad = np.zeros(n_verts)

        if props.vertex_group_diff_a != '': diff_a = np.zeros(n_verts)
        if props.vertex_group_diff_b != '': diff_b = np.zeros(n_verts)
        if props.vertex_group_scale != '': scale = np.zeros(n_verts)
        if props.vertex_group_f != '': f = np.zeros(n_verts)
        if props.vertex_group_k != '': k = np.zeros(n_verts)
        if props.vertex_group_brush != '': brush = np.zeros(n_verts)
        else: brush = 0

        a = bmesh_get_weight_numpy(group_index_a, dvert_lay, bm.verts)
        b = bmesh_get_weight_numpy(group_index_b, dvert_lay, bm.verts)

        if props.vertex_group_diff_a != '':
            group_index = ob.vertex_groups[props.vertex_group_diff_a].index
            diff_a = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)
            vg_bounds = (1,0) if props.invert_vertex_group_diff_a else (0,1)
            diff_a = np.interp(diff_a, vg_bounds, (props.min_diff_a, props.max_diff_a))

        if props.vertex_group_diff_b != '':
            group_index = ob.vertex_groups[props.vertex_group_diff_b].index
            diff_b = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)
            vg_bounds = (1,0) if props.invert_vertex_group_diff_b else (0,1)
            diff_b = np.interp(diff_b, vg_bounds, (props.min_diff_b, props.max_diff_b))

        if props.vertex_group_scale != '':
            group_index = ob.vertex_groups[props.vertex_group_scale].index
            scale = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)
            vg_bounds = (1,0) if props.invert_vertex_group_scale else (0,1)
            scale = np.interp(scale, vg_bounds, (props.min_scale, props.max_scale))

        if props.vertex_group_f != '':
            group_index = ob.vertex_groups[props.vertex_group_f].index
            f = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)
            vg_bounds = (1,0) if props.invert_vertex_group_f else (0,1)
            f = np.interp(f, vg_bounds, (props.min_f, props.max_f))

        if props.vertex_group_k != '':
            group_index = ob.vertex_groups[props.vertex_group_k].index
            k = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)
            vg_bounds = (1,0) if props.invert_vertex_group_k else (0,1)
            k = np.interp(k, vg_bounds, (props.min_k, props.max_k))

        if props.vertex_group_brush != '':
            group_index = ob.vertex_groups[props.vertex_group_brush].index
            brush = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)
            brush *= brush_mult

        if False:
            group_index = ob.vertex_groups['gradient'].index
            gradient = bmesh_get_weight_numpy(group_index, dvert_lay, bm.verts)

        #timeElapsed = time.time() - start
        #print('RD - Read Vertex Groups:',timeElapsed)
        #start = time.time()

        diff_a *= scale
        diff_b *= scale

        edge_verts = [0]*n_edges*2
        me.edges.foreach_get("vertices", edge_verts)

        gradient = get_uv_edge_vectors(me)
        uv_dir = Vector((0.5,0.5,0))
        #gradient = [abs(g.dot(uv_dir)) for g in gradient]
        gradient = [max(0,g.dot(uv_dir)) for g in gradient]

        timeElapsed = time.time() - start
        print('       Preparation Time:',timeElapsed)
        start = time.time()


        try:
            edge_verts = np.array(edge_verts)
            _f = f if type(f) is np.ndarray else np.array((f,))
            _k = k if type(k) is np.ndarray else np.array((k,))
            _diff_a = diff_a if type(diff_a) is np.ndarray else np.array((diff_a,))
            _diff_b = diff_b if type(diff_b) is np.ndarray else np.array((diff_b,))
            _brush = brush if type(brush) is np.ndarray else np.array((brush,))

            #a, b = numba_reaction_diffusion_anisotropic(n_verts, n_edges, edge_verts, a, b, _brush, _diff_a, _diff_b, _f, _k, dt, time_steps, gradient)
            a, b = numba_reaction_diffusion(n_verts, n_edges, edge_verts, a, b, _brush, _diff_a, _diff_b, _f, _k, dt, time_steps)

        except:
            print('Not using Numba! The simulation could be slow.')
            edge_verts = np.array(edge_verts)
            arr = np.arange(n_edges)*2
            id0 = edge_verts[arr]     # first vertex indices for each edge
            id1 = edge_verts[arr+1]   # second vertex indices for each edge
            for i in range(time_steps):
                b += brush
                lap_a = np.zeros(n_verts)
                lap_b = np.zeros(n_verts)
                lap_a0 =  a[id1] -  a[id0]   # laplacian increment for first vertex of each edge
                lap_b0 =  b[id1] -  b[id0]   # laplacian increment for first vertex of each edge

                np.add.at(lap_a, id0, lap_a0)
                np.add.at(lap_b, id0, lap_b0)
                np.add.at(lap_a, id1, -lap_a0)
                np.add.at(lap_b, id1, -lap_b0)

                ab2 = a*b**2
                a += eval("(diff_a*lap_a - ab2 + f*(1-a))*dt")
                b += eval("(diff_b*lap_b + ab2 - (k+f)*b)*dt")
                #a += (diff_a*lap_a - ab2 + f*(1-a))*dt
                #b += (diff_b*lap_b + ab2 - (k+f)*b)*dt

                a = nan_to_num(a)
                b = nan_to_num(b)

        timeElapsed = time.time() - start
        print('       Simulation Time:',timeElapsed)
        start = time.time()

    if bake:
        if not(os.path.exists(folder)):
            os.mkdir(folder)
        file_name = folder / "a_{:04d}".format(scene.frame_current)
        a.tofile(file_name)
        file_name = folder / "b_{:04d}".format(scene.frame_current)
        b.tofile(file_name)
    elif props.bool_cache:
        try:
            file_name = folder / "a_{:04d}".format(scene.frame_current)
            a = np.fromfile(file_name)
            file_name = folder / "b_{:04d}".format(scene.frame_current)
            b = np.fromfile(file_name)
        except: return

    if ob.mode == 'WEIGHT_PAINT':
        # slower, but prevent crashes
        vg_a = ob.vertex_groups['A']
        vg_b = ob.vertex_groups['B']
        for i in range(n_verts):
            vg_a.add([i], a[i], 'REPLACE')
            vg_b.add([i], b[i], 'REPLACE')
    else:
        if props.bool_mod:
            bm.free()               # release old bmesh
            bm = bmesh.new()        # create an empty BMesh
            bm.from_mesh(ob.data)   # fill it in from a Mesh
            dvert_lay = bm.verts.layers.deform.active
        # faster, but can cause crashes while painting weight
        for i, v in enumerate(bm.verts):
            dvert = v[dvert_lay]
            dvert[group_index_a] = a[i]
            dvert[group_index_b] = b[i]
        bm.to_mesh(ob.data)

    if 'A' in ob.data.vertex_colors or 'B' in ob.data.vertex_colors:
        v_id = np.array([v for p in ob.data.polygons for v in p.vertices])

        if 'B' in ob.data.vertex_colors:
            c_val = b[v_id]
            c_val = np.repeat(c_val, 4, axis=0)
            vc = ob.data.vertex_colors['B']
            vc.data.foreach_set('color',c_val.tolist())

        if 'A' in ob.data.vertex_colors:
            c_val = a[v_id]
            c_val = np.repeat(c_val, 4, axis=0)
            vc = ob.data.vertex_colors['A']
            vc.data.foreach_set('color',c_val.tolist())

    for ps in ob.particle_systems:
        if ps.vertex_group_density == 'B' or ps.vertex_group_density == 'A':
            ps.invert_vertex_group_density = not ps.invert_vertex_group_density
            ps.invert_vertex_group_density = not ps.invert_vertex_group_density

    if props.bool_mod: bpy.data.meshes.remove(me)
    bm.free()
    timeElapsed = time.time() - start
    print('       Closing Time:',timeElapsed)

class TISSUE_PT_reaction_diffusion(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_label = "Tissue Reaction-Diffusion"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return 'A' and 'B' in context.object.vertex_groups

    def draw(self, context):
        reaction_diffusion_add_handler(self, context)

        ob = context.object
        props = ob.reaction_diffusion_settings
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        if not ("A" and "B" in ob.vertex_groups):
            row.operator("object.start_reaction_diffusion",
                        icon="EXPERIMENTAL",
                        text="Reaction-Diffusion")
        else:
            row.operator("object.start_reaction_diffusion",
                        icon="EXPERIMENTAL",
                        text="Reset Reaction-Diffusion")
            row = col.row(align=True)
            row.prop(props, "run", text="Run Reaction-Diffusion")
            col = layout.column(align=True)
            row = col.row(align=True)
            row.prop(props, "time_steps")
            row.prop(props, "dt")
            row.enabled = not props.bool_cache
            col.separator()
            row = col.row(align=True)
            col1 = row.column(align=True)
            col1.prop(props, "diff_a")
            col1.enabled = props.vertex_group_diff_a == '' and not props.bool_cache
            col1 = row.column(align=True)
            col1.prop(props, "diff_b")
            col1.enabled = props.vertex_group_diff_b == '' and not props.bool_cache
            row = col.row(align=True)
            row.prop(props, "diff_mult")
            row.enabled = props.vertex_group_scale == '' and not props.bool_cache
            #col.separator()
            row = col.row(align=True)
            col1 = row.column(align=True)
            col1.prop(props, "f")
            col1.enabled = props.vertex_group_f == '' and not props.bool_cache
            col1 = row.column(align=True)
            col1.prop(props, "k")
            col1.enabled = props.vertex_group_k == '' and not props.bool_cache
            col.separator()
            col.label(text='Cache:')
            #col.prop(props, "bool_cache")
            col.prop(props, "cache_dir", text='')
            col.separator()
            row = col.row(align=True)
            row.prop(props, "cache_frame_start")
            row.prop(props, "cache_frame_end")
            col.separator()
            if props.bool_cache:
                col.operator("object.reaction_diffusion_free_data")
            else:
                row = col.row(align=True)
                row.operator("object.bake_reaction_diffusion")
                file = bpy.context.blend_data.filepath
                temp = bpy.context.preferences.filepaths.temporary_directory
                if file == temp == props.cache_dir == '':
                    row.enabled = False
                    col.label(text="Cannot use cache", icon='ERROR')
                    col.label(text='please save the Blender or set a Cache directory')

            #col.prop_search(props, 'vertex_group_diff_a', ob, "vertex_groups", text='Diff A')
            #col.prop_search(props, 'vertex_group_diff_b', ob, "vertex_groups", text='Diff B')
            #col.prop_search(props, 'vertex_group_scale', ob, "vertex_groups", text='Scale')
            #col.prop_search(props, 'vertex_group_f', ob, "vertex_groups", text='f')
            #col.prop_search(props, 'vertex_group_k', ob, "vertex_groups", text='k')


class TISSUE_PT_reaction_diffusion_weight(Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_parent_id = "TISSUE_PT_reaction_diffusion"
    bl_label = "Vertex Groups"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return 'A' and 'B' in context.object.vertex_groups

    def draw(self, context):
        ob = context.object
        props = ob.reaction_diffusion_settings
        layout = self.layout
        #layout.use_property_split = True
        col = layout.column(align=True)
        col.prop(props, "bool_mod")
        col.separator()
        insert_weight_parameter(col, ob, 'brush', text='Brush:')
        insert_weight_parameter(col, ob, 'diff_a', text='Diff A:')
        insert_weight_parameter(col, ob, 'diff_b', text='Diff B:')
        insert_weight_parameter(col, ob, 'scale', text='Scale:')
        insert_weight_parameter(col, ob, 'f', text='f:')
        insert_weight_parameter(col, ob, 'k', text='k:')
        col.enabled = not props.bool_cache

def insert_weight_parameter(col, ob, name, text=''):
    props = ob.reaction_diffusion_settings
    split = col.split(factor=0.25, align=True)
    col2 = split.column(align=True)
    col2.label(text=text)
    col2 = split.column(align=True)
    row2 = col2.row(align=True)
    row2.prop_search(props, 'vertex_group_' + name, ob, "vertex_groups", text='')
    if name != 'brush':
        row2.prop(props, "invert_vertex_group_" + name, text="", toggle=True, icon='ARROW_LEFTRIGHT')
    if 'vertex_group_' + name in props:
        if props['vertex_group_' + name] != '':
            if name == 'brush':
                col2.prop(props, "brush_mult")
            else:
                row2 = col2.row(align=True)
                row2.prop(props, "min_" + name, text="Min")
                row2 = col2.row(align=True)
                row2.prop(props, "max_" + name, text="Max")
    col.separator()

if False:
    @jit(["float64[:,:](int32, int32, float64, float64, boolean, int32, float64, float64[:,:], float64[:,:], int32[:,:], float64[:], float64[:])"]) #(nopython=True, parallel=True)
    def contour_edges_pattern(in_steps, out_steps, in_displace, out_displace, limit_z, c, iso_val, vertices, normals, filtered_edges, weight, pattern_weight):
        # vertices indexes
        id0 = filtered_edges[:,0]
        id1 = filtered_edges[:,1]
        # vertices weight
        w0 = weight[id0]
        w1 = weight[id1]
        # weight condition
        bool_w0 = w0 < iso_val
        bool_w1 = w1 < iso_val

        # mask all edges that have one weight value below the iso value
        mask_new_verts = np.logical_xor(bool_w0, bool_w1)
        out_array = np.array([[0]]).astype(type='float64', order='A')
        if not mask_new_verts.any(): return out_array, out_array, out_array

        id0 = id0[mask_new_verts]
        id1 = id1[mask_new_verts]
        # filter arrays
        v0 = vertices[id0]
        v1 = vertices[id1]
        n0 = normals[id0]
        n1 = normals[id1]
        w0 = w0[mask_new_verts]
        w1 = w1[mask_new_verts]
        pattern0 = pattern_weight[id0]
        pattern1 = pattern_weight[id1]
        param = (iso_val-w0)/(w1-w0)
        # pattern displace
        #mult = 1 if c%2 == 0 else -1
        if c%(in_steps + out_steps) < in_steps:
            mult = in_displace
        else:
            mult = out_displace
        pattern_value = pattern0 + (pattern1-pattern0)*param
        disp = pattern_value * mult
        param2 = np.expand_dims(param,axis=1)
        #param = param2
        disp2 = np.expand_dims(disp,axis=1)
        #disp = disp2
        verts = v0 + (v1-v0)*param2
        norm = n0 + (n1-n0)*param2
        if limit_z:
            norm2 = np.expand_dims(norm[:,2], axis=1)
            limit_mult = 1-np.absolute(norm2)
            disp2 *= limit_mult
        verts = verts + norm*disp2

        # indexes of edges with new vertices
        edges_index = filtered_edges[mask_new_verts][:,2]

        # remove all edges completely below the iso value
        mask_edges = np.logical_not(np.logical_and(bool_w0, bool_w1))

        _filtered_edges = filtered_edges[mask_edges]
        filtered_edges = _filtered_edges.astype(type='float64', order='A')

        _edges_index = np.expand_dims(edges_index,axis=0)
        _edges_index = _edges_index.astype(type='float64', order='A')

        _verts = verts.astype(type='float64', order='A')
        return _filtered_edges, _edges_index, _verts

def contour_edges_pattern(operator, c, verts_count, iso_val, vertices, normals, filtered_edges, weight, pattern_weight, bevel_weight):
    # vertices indexes
    id0 = filtered_edges[:,0]
    id1 = filtered_edges[:,1]
    # vertices weight
    w0 = weight[id0]
    w1 = weight[id1]
    # weight condition
    bool_w0 = w0 < iso_val
    bool_w1 = w1 < iso_val

    # mask all edges that have one weight value below the iso value
    mask_new_verts = np.logical_xor(bool_w0, bool_w1)
    if not mask_new_verts.any():
        return np.array([[None]]), {}, np.array([[None]]), np.array([[None]])

    id0 = id0[mask_new_verts]
    id1 = id1[mask_new_verts]
    # filter arrays
    v0 = vertices[id0]
    v1 = vertices[id1]
    n0 = normals[id0]
    n1 = normals[id1]
    w0 = w0[mask_new_verts]
    w1 = w1[mask_new_verts]
    pattern0 = pattern_weight[id0]
    pattern1 = pattern_weight[id1]
    try:
        bevel0 = bevel_weight[id0]
        bevel1 = bevel_weight[id1]
    except: pass
    param = (iso_val-w0)/(w1-w0)
    # pattern displace
    #mult = 1 if c%2 == 0 else -1
    if c%(operator.in_steps + operator.out_steps) < operator.in_steps:
        mult = operator.in_displace
    else:
        mult = operator.out_displace
    pattern_value = pattern0 + (pattern1-pattern0)*param
    try:
        bevel_value = bevel0 + (bevel1-bevel0)*param
        bevel_value = np.expand_dims(bevel_value,axis=1)
    except: bevel_value = None
    disp = pattern_value * mult
    param = np.expand_dims(param,axis=1)
    disp = np.expand_dims(disp,axis=1)
    verts = v0 + (v1-v0)*param
    norm = n0 + (n1-n0)*param
    if operator.limit_z: disp *= 1-abs(np.expand_dims(norm[:,2], axis=1))
    verts = verts + norm*disp

    # indexes of edges with new vertices
    edges_index = filtered_edges[mask_new_verts][:,2]

    # remove all edges completely below the iso value
    #mask_edges = np.logical_not(np.logical_and(bool_w0, bool_w1))
    #filtered_edges = filtered_edges[mask_edges]
    return filtered_edges, edges_index, verts, bevel_value

def contour_edges_pattern_eval(operator, c, verts_count, iso_val, vertices, normals, filtered_edges, weight, pattern_weight):
    # vertices indexes
    id0 = eval('filtered_edges[:,0]')
    id1 = eval('filtered_edges[:,1]')
    # vertices weight
    w0 = eval('weight[id0]')
    w1 = eval('weight[id1]')
    # weight condition
    bool_w0 = ne.evaluate('w0 < iso_val')
    bool_w1 = ne.evaluate('w1 < iso_val')

    # mask all edges that have one weight value below the iso value
    mask_new_verts = eval('np.logical_xor(bool_w0, bool_w1)')
    if not mask_new_verts.any(): return np.array([[None]]), {}, np.array([[None]])

    id0 = eval('id0[mask_new_verts]')
    id1 = eval('id1[mask_new_verts]')
    # filter arrays
    v0 = eval('vertices[id0]')
    v1 = eval('vertices[id1]')
    n0 = eval('normals[id0]')
    n1 = eval('normals[id1]')
    w0 = eval('w0[mask_new_verts]')
    w1 = eval('w1[mask_new_verts]')
    pattern0 = eval('pattern_weight[id0]')
    pattern1 = eval('pattern_weight[id1]')
    param = ne.evaluate('(iso_val-w0)/(w1-w0)')
    # pattern displace
    #mult = 1 if c%2 == 0 else -1
    if c%(operator.in_steps + operator.out_steps) < operator.in_steps:
        mult = -operator.in_displace
    else:
        mult = operator.out_displace
    pattern_value = eval('pattern0 + (pattern1-pattern0)*param')
    disp = ne.evaluate('pattern_value * mult')
    param = eval('np.expand_dims(param,axis=1)')
    disp = eval('np.expand_dims(disp,axis=1)')
    verts = ne.evaluate('v0 + (v1-v0)*param')
    norm = ne.evaluate('n0 + (n1-n0)*param')
    if operator.limit_z:
        mult = eval('1-abs(np.expand_dims(norm[:,2], axis=1))')
        disp = ne.evaluate('disp * mult')
    verts = ne.evaluate('verts + norm*disp')

    # indexes of edges with new vertices
    edges_index = eval('filtered_edges[mask_new_verts][:,2]')

    # remove all edges completely below the iso value
    mask_edges = eval('np.logical_not(np.logical_and(bool_w0, bool_w1))')
    filtered_edges = eval('filtered_edges[mask_edges]')
    return filtered_edges, edges_index, verts


def contour_bmesh(me, bm, weight, iso_val):
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # store weight values

    vertices = get_vertices_numpy(me)
    faces_mask = np.array(bm.faces)
    filtered_edges = get_edges_id_numpy(me)
    n_verts = len(bm.verts)

    #############################

    # vertices indexes
    id0 = filtered_edges[:,0]
    id1 = filtered_edges[:,1]
    # vertices weight
    w0 = weight[id0]
    w1 = weight[id1]
    # weight condition
    bool_w0 = w0 < iso_val
    bool_w1 = w1 < iso_val

    # mask all edges that have one weight value below the iso value
    mask_new_verts = np.logical_xor(bool_w0, bool_w1)
    if not mask_new_verts.any(): return np.array([[None]]), {}, np.array([[None]])

    id0 = id0[mask_new_verts]
    id1 = id1[mask_new_verts]
    # filter arrays
    v0 = vertices[id0]
    v1 = vertices[id1]
    w0 = w0[mask_new_verts]
    w1 = w1[mask_new_verts]
    param = (iso_val-w0)/(w1-w0)
    param = np.expand_dims(param,axis=1)
    verts = v0 + (v1-v0)*param

    # indexes of edges with new vertices
    #edges_index = filtered_edges[mask_new_verts][:,2]

    edges_id = {}
    for i, e in enumerate(filtered_edges):
        #edges_id[id] = i + n_verts
        edges_id['{}_{}'.format(e[0],e[1])] = i + n_verts
        edges_id['{}_{}'.format(e[1],e[0])] = i + n_verts


    '''
    for e in filtered_edges:
        id0 = e.verts[0].index
        id1 = e.verts[1].index
        w0 = weight[id0]
        w1 = weight[id1]

        if w0 == w1: continue
        elif w0 > iso_val and w1 > iso_val:
            continue
        elif w0 < iso_val and w1 < iso_val: continue
        elif w0 == iso_val or w1 == iso_val: continue
        else:
            v0 = me0.vertices[id0].co
            v1 = me0.vertices[id1].co
            v = v0.lerp(v1, (iso_val-w0)/(w1-w0))
            delete_edges.append(e)
            verts.append(v)
            edges_id[str(id0)+"_"+str(id1)] = count
            edges_id[str(id1)+"_"+str(id0)] = count
            count += 1
    '''

    splitted_faces = []

    switch = False
    # splitting faces
    for f in faces_mask:
        # create sub-faces slots. Once a new vertex is reached it will
        # change slot, storing the next vertices for a new face.
        build_faces = [[],[]]
        #switch = False
        verts0 = list(me.polygons[f.index].vertices)
        verts1 = list(verts0)
        verts1.append(verts1.pop(0)) # shift list
        for id0, id1 in zip(verts0, verts1):

            # add first vertex to active slot
            build_faces[switch].append(id0)

            # try to split edge
            try:
                # check if the edge must be splitted
                new_vert = edges_id['{}_{}'.format(id0,id1)]
                # add new vertex
                build_faces[switch].append(new_vert)
                # if there is an open face on the other slot
                if len(build_faces[not switch]) > 0:
                    # store actual face
                    splitted_faces.append(build_faces[switch])
                    # reset actual faces and switch
                    build_faces[switch] = []
                    # change face slot
                switch = not switch
                # continue previous face
                build_faces[switch].append(new_vert)
            except: pass
        if len(build_faces[not switch]) == 2:
            build_faces[not switch].append(id0)
        if len(build_faces[not switch]) > 2:
            splitted_faces.append(build_faces[not switch])
        # add last face
        splitted_faces.append(build_faces[switch])

    # adding new vertices use fast local method access
    _new_vert = bm.verts.new
    for v in verts: _new_vert(v)
    bm.verts.ensure_lookup_table()

    # deleting old edges/faces
    bm.edges.ensure_lookup_table()
    remove_edges = [bm.edges[i] for i in filtered_edges[:,2]]
    #for e in remove_edges: bm.edges.remove(e)
    #for e in delete_edges: bm.edges.remove(e)

    bm.verts.ensure_lookup_table()
    # adding new faces use fast local method access
    _new_face = bm.faces.new
    missed_faces = []
    for f in splitted_faces:
        try:
            face_verts = [bm.verts[i] for i in f]
            _new_face(face_verts)
        except:
            missed_faces.append(f)

    #me = bpy.data.meshes.new('_tissue_tmp_')
    bm.to_mesh(me)
    weight = np.concatenate((weight, np.ones(len(verts))*iso_val))

    return me, bm, weight




class tissue_weight_streamlines(Operator):
    bl_idname = "object.tissue_weight_streamlines"
    bl_label = "Streamlines Curves"
    bl_description = ("")
    bl_options = {'REGISTER', 'UNDO'}

    mode : EnumProperty(
        items=(
            ('VERTS', "Verts", "Follow vertices"),
            ('EDGES', "Edges", "Follow Edges")
            ),
        default='VERTS',
        name="Streamlines path mode"
        )

    interpolation : EnumProperty(
        items=(
            ('POLY', "Poly", "Generate Polylines"),
            ('NURBS', "NURBS", "Generate Nurbs curves")
            ),
        default='POLY',
        name="Interpolation mode"
        )

    use_modifiers : BoolProperty(
        name="Use Modifiers", default=True,
        description="Apply all the modifiers")

    use_selected : BoolProperty(
        name="Use Selected Vertices", default=False,
        description="Use selected vertices as Seed")

    same_weight : BoolProperty(
        name="Same Weight", default=True,
        description="Continue the streamlines when the weight is the same")

    min_iso : FloatProperty(
        name="Min Value", default=0., soft_min=0, soft_max=1,
        description="Minimum weight value")
    max_iso : FloatProperty(
        name="Max Value", default=1, soft_min=0, soft_max=1,
        description="Maximum weight value")

    rand_seed : IntProperty(
        name="Seed", default=0, min=0, soft_max=10,
        description="Random Seed")
    n_curves : IntProperty(
        name="Curves", default=50, soft_min=1, soft_max=100000,
        description="Number of Curves")
    min_rad = 1
    max_rad = 1

    pos_steps : IntProperty(
        name="High Steps", default=50, min=0, soft_max=100,
        description="Number of steps in the direction of high weight")
    neg_steps : IntProperty(
        name="Low Steps", default=50, min=0, soft_max=100,
        description="Number of steps in the direction of low weight")

    bevel_depth : FloatProperty(
        name="Bevel Depth", default=0, min=0, soft_max=1,
        description="")
    min_bevel_depth : FloatProperty(
        name="Min Bevel Depth", default=0.1, min=0, soft_max=1,
        description="")
    max_bevel_depth : FloatProperty(
        name="Max Bevel Depth", default=1, min=0, soft_max=1,
        description="")

    rand_dir : FloatProperty(
        name="Randomize", default=0, min=0, max=1,
        description="Randomize streamlines directions (Slower)")

    vertex_group_seeds : StringProperty(
        name="Displace", default='',
        description="Vertex Group used for pattern displace")

    vertex_group_bevel : StringProperty(
        name="Bevel", default='',
        description="Variable Bevel depth")

    object_name : StringProperty(
        name="Active Object", default='',
        description="")

    try: vg_name = bpy.context.object.vertex_groups.active.name
    except: vg_name = ''

    vertex_group_streamlines : StringProperty(
        name="Flow", default=vg_name,
        description="Vertex Group used for streamlines")

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and len(ob.vertex_groups) > 0 or ob.type == 'CURVE'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        if not context.object.type == 'CURVE':
            self.object_name = context.object.name
        ob = bpy.data.objects[self.object_name]
        if self.vertex_group_streamlines not in [vg.name for vg in ob.vertex_groups]:
            self.vertex_group_streamlines = ob.vertex_groups.active.name
        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, 'mode', expand=True,
            slider=True, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        col.prop(self, "use_modifiers")
        col.label(text="Streamlines Curves:")
        row = col.row(align=True)
        row.prop(self, 'interpolation', expand=True,
            slider=True, toggle=False, icon_only=False, event=False,
            full_event=False, emboss=True, index=-1)
        col.separator()
        col.prop_search(self, 'vertex_group_streamlines', ob, "vertex_groups", text='')
        if not (self.use_selected or context.mode == 'EDIT_MESH'):
            row = col.row(align=True)
            row.prop(self,'n_curves')
            #row.enabled = context.mode != 'EDIT_MESH'
            row = col.row(align=True)
            row.prop(self,'rand_seed')
            #row.enabled = context.mode != 'EDIT_MESH'
        row = col.row(align=True)
        row.prop(self,'neg_steps')
        row.prop(self,'pos_steps')
        #row = col.row(align=True)
        #row.prop(self,'min_iso')
        #row.prop(self,'max_iso')
        col.prop(self, "same_weight")
        col.separator()
        col.label(text='Curves Bevel:')
        col.prop_search(self, 'vertex_group_bevel', ob, "vertex_groups", text='')
        if self.vertex_group_bevel != '':
            row = col.row(align=True)
            row.prop(self,'min_bevel_depth')
            row.prop(self,'max_bevel_depth')
        else:
            col.prop(self,'bevel_depth')
        col.separator()
        col.prop(self, "rand_dir")

    def execute(self, context):
        start_time = timeit.default_timer()
        try:
            check = context.object.vertex_groups[0]
        except:
            self.report({'ERROR'}, "The object doesn't have Vertex Groups")
            return {'CANCELLED'}
        ob = bpy.data.objects[self.object_name]
        ob.select_set(False)

        dg = context.evaluated_depsgraph_get()
        ob = ob.evaluated_get(dg)
        me = ob.data
        n_verts = len(me.vertices)
        n_edges = len(me.edges)
        n_faces = len(me.polygons)

        # generate new bmesh
        #bm = bmesh.new()
        #bm.from_mesh(me)

        # store weight values
        try:
            weight = get_weight_numpy(ob.vertex_groups[self.vertex_group_streamlines], n_verts)
        except:
            bm.free()
            self.report({'ERROR'}, "Please select a Vertex Group for streamlines")
            return {'CANCELLED'}

        variable_bevel = False
        bevel_weight = None
        bevel_depth = self.bevel_depth
        try:
            if self.min_bevel_depth == self.max_bevel_depth:
                #bevel_weight = np.ones((n_verts))
                bevel_depth = self.min_bevel_depth
            else:
                b0 = min(self.min_bevel_depth, self.max_bevel_depth)
                b1 = max(self.min_bevel_depth, self.max_bevel_depth)
                bevel_weight = get_weight_numpy(ob.vertex_groups[self.vertex_group_bevel], n_verts)
                if self.min_bevel_depth > self.max_bevel_depth:
                    bevel_weight = 1-bevel_weight
                bevel_weight = b0/b1 + bevel_weight*((b1-b0)/b1)
                bevel_depth = b1
            variable_bevel = True
        except:
            pass#bevel_weight = np.ones((n_verts))

        seeds = []

        if bpy.context.mode == 'EDIT_MESH':
            self.use_selected = True
            bpy.ops.object.mode_set(mode='OBJECT')
            ob = bpy.context.object
            me = simple_to_mesh(ob)
            for v in me.vertices:
                if v.select: seeds.append(v.index)

        if not seeds:
            np.random.seed(self.rand_seed)
            seeds = np.random.randint(n_verts, size=self.n_curves)

        #weight = np.array(get_weight(ob.vertex_groups.active, n_verts))

        curves_pts = []
        curves_weight = []

        neigh = [[] for i in range(n_verts)]
        if self.mode == 'EDGES':
            # store neighbors
            for e in me.edges:
                ev = e.vertices
                neigh[ev[0]].append(ev[1])
                neigh[ev[1]].append(ev[0])

        elif self.mode == 'VERTS':
            # store neighbors
            for p in me.polygons:
                face_verts = [v for v in p.vertices]
                for i in range(len(face_verts)):
                    fv = face_verts.copy()
                    neigh[fv.pop(i)] += fv

        neigh_weight = [weight[n].tolist() for n in neigh]

        # evaluate direction
        next_vert = [-1]*n_verts

        if self.rand_dir > 0:
            for i in range(n_verts):
                n = neigh[i]
                nw = neigh_weight[i]
                sorted_nw = neigh_weight[i].copy()
                sorted_nw.sort()
                for w in sorted_nw:
                    neigh[i] = [n[nw.index(w)] for w in sorted_nw]
        else:
            if self.pos_steps > 0:
                for i in range(n_verts):
                    n = neigh[i]
                    nw = neigh_weight[i]
                    max_w = max(nw)
                    if self.same_weight:
                        if max_w >= weight[i]:
                            next_vert[i] = n[nw.index(max(nw))]
                    else:
                        if max_w > weight[i]:
                            next_vert[i] = n[nw.index(max(nw))]

            if self.neg_steps > 0:
                prev_vert = [-1]*n_verts
                for i in range(n_verts):
                    n = neigh[i]
                    nw = neigh_weight[i]
                    min_w = min(nw)
                    if self.same_weight:
                        if min_w <= weight[i]:
                            prev_vert[i] = n[nw.index(min(nw))]
                    else:
                        if min_w < weight[i]:
                            prev_vert[i] = n[nw.index(min(nw))]

        co = [0]*3*n_verts
        me.vertices.foreach_get('co', co)
        co = np.array(co).reshape((-1,3))

        # create streamlines
        curves = []
        for i in seeds:
            next_pts = [i]
            for j in range(self.pos_steps):
                if self.rand_dir > 0:
                    n = neigh[next_pts[-1]]
                    next = n[int(len(n) * (1-random.random() * self.rand_dir))]
                else:
                    next = next_vert[next_pts[-1]]
                if next > 0:
                    if next not in next_pts: next_pts.append(next)
                else: break

            prev_pts = [i]
            for j in range(self.neg_steps):
                if self.rand_dir > 0:
                    n = neigh[prev_pts[-1]]
                    prev = n[int(len(n) * random.random() * self.rand_dir)]
                else:
                    prev = prev_vert[prev_pts[-1]]
                if prev > 0:
                    if prev not in prev_pts:
                        prev_pts.append(prev)
                else: break

            next_pts = np.array(next_pts).astype('int')
            prev_pts = np.flip(prev_pts[1:]).astype('int')
            all_pts = np.concatenate((prev_pts, next_pts))
            if len(all_pts) > 1:
                curves.append(all_pts)
        crv = nurbs_from_vertices(curves, co, bevel_weight, ob.name + '_Streamlines', True, self.interpolation)
        crv.data.bevel_depth = bevel_depth
        crv.matrix_world = ob.matrix_world

        print("Streamlines Curves, total time: " + str(timeit.default_timer() - start_time) + " sec")
        return {'FINISHED'}
