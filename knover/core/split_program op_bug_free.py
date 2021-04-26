import paddle.distributed.fleet as fleet
import paddle.fluid.layers as layers
import paddle.fluid as fluid
import paddle.fluid.core as core
# 修改了_find_var_recursive(str(var))会在不止当前block寻找var的bug
used_var_set = set()
def op_inputs(op, src_block, dst_block):
    global used_var_set
    inputs = {}
    for i in range(0, len(op.input_names)):
        val = op.input(op.input_names[i])
        inputs[op.input_names[i]] = val
    vars = op.desc.input_arg_names()
    for var in vars:
        print("************" + str(var))
        if var in used_var_set or "_blocking_queue" in var:
            print(str(var), "input in used_var_set")
            continue
        used_var_set.add(var)

        if dst_block.has_var(str(var)):
            print(str(var), "input find")
            continue
            
        source_var = src_block._var_recursive(str(var))
        if source_var.type == core.VarDesc.VarType.READER:
            dst_var= dst_block.create_var(name=var, type=core.VarDesc.VarType.READER, persistable=source_var.persistable)
        else:
            dst_var = dst_block._clone_variable(source_var, False)
        print("===========创建+++++++++++++++++", str(var))
        dst_var.stop_gradient = source_var.stop_gradient
    return inputs

def op_outputs(op, src_block, dst_block):
    global used_var_set
    outputs = {}
    for i in range(0, len(op.output_names)):
        val = op.output(op.output_names[i])
        outputs[op.output_names[i]] = val
    vars = op.desc.output_arg_names()
    for var in vars:
        if var in used_var_set or "_blocking_queue" in var:
            print(str(var), "output in used_var_set")
            continue
        used_var_set.add(var)
        if dst_block.has_var(str(var)):
            print(str(var), "output find")
            continue
        source_var = src_block._var_recursive(str(var))
        if source_var.type == core.VarDesc.VarType.READER:
            dst_var= dst_block.create_var(name=var, type=core.VarDesc.VarType.READER, persistable=source_var.persistable)
        else:
            dst_var = dst_block._clone_variable(source_var, False)
        print("===========创建+++++++++++++++++", str(var))
        dst_var.stop_gradient = source_var.stop_gradient
    return outputs

def fuse_var(src_block, dst_block):
    pass

# 用于将一个src_program的op赋值给另一个dst_program
def replace(src_program, dst_program, \
    src_block_id=0, dst_block_id=1, \
    src_block_start_op_idx=12, \
    src_block_end_op_idx=None, \
    dst_block_start_op_idx=None, \
    dst_block_end_op_idx=None):
    # global used_var_set
    src_block = src_program.block(src_block_id)
    dst_block = dst_program.block(dst_block_id)
    with open("dst.txt", "w") as f:
        f.write(str(dst_block.program))
        print("sharding_program ================")
    with open("src.txt", "w") as f:
        f.write(str(src_block.program))
        print("sharding_program ================")
    src_ops = src_block.ops
    dst_ops = dst_block.ops
    if src_block_start_op_idx is None:
        src_block_start_op_idx = 0
    if src_block_end_op_idx is None:
        src_block_end_op_idx = len(src_ops)
    if dst_block_start_op_idx is None:
        dst_block_start_op_idx = 0
    if dst_block_end_op_idx is None:
        dst_block_end_op_idx = len(dst_ops)
    
    # 修改src_block的名字
    # dst_op_pointer = dst_block_start_op_idx
    # for i in range(src_block_start_op_idx, src_block_end_op_idx):
    #     src_op = src_ops[i]
    #     # print(str(i), src_op.type)
    #     if str(src_op.type) in ["c_sync_calc_stream", "c_sync_comm_stream", "c_broadcast"]:
    #         continue       
    #     dst_op = dst_ops[dst_op_pointer]
    #     if src_op.type != dst_op.type:
    #         continue
    #     print("src_i: " + str(i) + "=========================" + "dst_op_pointer: " + str(dst_op_pointer) + "type: " + str(dst_op.type))
    #     assert src_op.type == dst_op.type, "src_op: {}, dst_op: {}, src_i: {}, dst_i: {}".format(src_op.type, dst_op.type, str(i), str(dst_op_pointer))
    #     src_vars = src_op.desc.input_arg_names() + src_op.desc.output_arg_names()
    #     dst_vars = dst_op.desc.input_arg_names() + dst_op.desc.output_arg_names()
    #     dst_var_pointer = 0
    #     for src_var in src_vars:
    #         # if "fill_constant" == src_op.type and  "BroadCast" in src_var:
    #         #     continue
    #         if str(dst_op_pointer) == "402":
    #             print(src_var, dst_vars[dst_var_pointer])
    #         src_block._rename_var(src_var, dst_vars[dst_var_pointer])
    #         dst_var_pointer += 1
    #     dst_op_pointer += 1
            
        

    for i in range(dst_block_end_op_idx-1, dst_block_start_op_idx-1, -1):
        dst_block._remove_op(i)

    for i in range(src_block_start_op_idx, src_block_end_op_idx):
        src_op = src_ops[i]
        dst_block._insert_op(dst_block_start_op_idx, type=src_op.type, attrs=src_op.all_attrs(), inputs=op_inputs(src_op, src_block, dst_block), outputs=op_outputs(src_op, src_block, dst_block))
        dst_block_start_op_idx += 1
    
    dst_block._sync_with_cpp()
    # 删除dst_block里面所有没有被用到的var
    vars = list(dst_block.vars.keys())
    for var in vars:
        if var not in used_var_set:
            dst_block._remove_var(var)


    with open("src_program.txt", "w") as f:
        f.write(str(src_program))
    with open("dst_program.txt", "w") as f:
        f.write(str(dst_program))
    return
    

        
