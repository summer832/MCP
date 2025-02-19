from codeGenerator import CodeGenerationInput, generate_code



input_data = CodeGenerationInput(queries=[

  '向学生表中插入一条数据，名字jack，年龄18',

  \# 可以添加更多查询

])

output = generate_code(input_data)



返回示例：

```
import { createConnection } from 'typeorm';
import { Student } from './entity/Student'; // 假设你有一个名为Student的实体

async function insertStudent() {
  const connection = await createConnection(); // 创建数据库连接

  const student = new Student(); // 创建一个新的学生实体
  student.name = 'jack'; // 设置学生的名字
  student.age = 18; // 设置学生的年龄

  await connection.manager.save(student); // 保存学生到数据库

  console.log('Student inserted successfully!');
  await connection.close(); // 关闭数据库连接
}

insertStudent().catch(error => console.error(error));
```

