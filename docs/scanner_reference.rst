扫描器参考
==========

扫描器文档被拆分为三个聚焦视图，以便更容易进行审查：

* :doc:`scanner_public_api`
  审查 ``supysonic/scanner.py`` 中的公开门面。

* :doc:`scanner_internal_flow`
  审查 ``supysonic/scanner_func`` 下的辅助层模块，以及当前的执行流程。

* :doc:`scanner_folder_scan_flow`
  按真实调用顺序审查“根文件夹进入扫描队列后会发生什么”。

在检查调用方可以直接调用的内容时，使用公开 API 页面。在审查实现细节、辅助边界以及当前行为中的特殊情况时，使用内部流程页面。在追踪一个根文件夹从入队到后处理的完整链路时，使用扫描流程页面。

.. toctree::
   :maxdepth: 2

   scanner_public_api
   scanner_internal_flow
   scanner_folder_scan_flow
