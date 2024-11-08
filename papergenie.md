## Global Input
- 论文主题
- 论文相关文件：{
    - 相关实验的数据
    - 实验记录文档
    - 参考资料
    - etc.
}

## 论文写作

### 调查

**Input**: {
    - 论文主题
    - 论文相关文件
}

根据论文主题和相关文件获取到一系列的相关论文：{
    - 获取渠道：{
        - Google Scholar
        - Arxiv
        - etc.
    }
}

**Output**: {
    - 一系列相关论文(Related Papers)
}

### 论文大纲(Outline)

**Input**: {
    - 论文主题
    - 论文相关文件
    - 一系列相关论文(Related Papers)
}
首先根据*论文主题*和*论文相关文件*生成Draft Outline

#### 视角引导
// 使用autogen GroupChat
生成N个带有不同视角的OutlineWriter agent，用于提出关于论文在不同视角上的问题
生成1个Expert agent，用于解答OutlineWriter agent，Expert agent需要：{
    - 拆解问题
    - 过滤论文中不需要的视角
    - 通过搜索获取OutlineWriter agent提出的问题
    - 在以及搜索到的相关论文中搜索问题
}
在经过N+1轮的讨论后(记作:{C0,C1,....CN}),由Expert agent根据对话的记录({C0,C1,....CN})和Draft Outline生成一个改进后的Outline，用于生成整篇论文,同时Expert需要根据在相关论文中搜索问题得到的答案对论文评估，以获取到可以作为论文Reference的Paper

**Output**: Outline

### Chart Generation
// 使用autogen code executor
**Input**：{
    - 实验数据
    - 统计数据
}

生成两个agent：{
    - code writer
    - code reviewer
}
code writer负责编写将data转为chart的代码，code reviewer负责给出一些代码的改进建议并尝试发现代码中的错误，最后在sandbox中运行代码以获取chart

**Output**：Charts

最后根据*论文大纲(Outline),参考文献(Reference Papers)以及Charts*得到一篇论文初稿

## 论文润色
// autogen Group chat
由N个Agent在一起讨论，以获取论文的修改意见，最后由一人进行拍板，获的终稿