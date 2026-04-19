import json
import os
import shutil

class JsonDataManager:
    def __init__(self, json_file_path):
        """
        初始化JSON数据管理器

        Args:
            json_file_path (str): JSON文件路径
        """
        self.json_file_path = json_file_path
        # 确保文件存在且具有基本结构
        self._ensure_file_exists()
        self.data = self._load_json()

    def _ensure_file_exists(self):
        """确保JSON文件存在，并且包含顶层的'data'键"""
        if not os.path.exists(self.json_file_path):
            # 如果文件不存在，创建一个带有空"data"列表的基础结构
            base_structure = {"data": []}
            with open(self.json_file_path, 'w', encoding='utf-8') as f:
                json.dump(base_structure, f, indent=4, ensure_ascii=False)
        else:
            # 如果文件存在，检查其结构是否正确
            try:
                with open(self.json_file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                # 如果文件存在但没有"data"键，则添加它
                if 'data' not in existing_data:
                    existing_data['data'] = []
                    with open(self.json_file_path, 'w', encoding='utf-8') as f:
                        json.dump(existing_data, f, indent=4, ensure_ascii=False)
            except (json.JSONDecodeError, Exception):
                # 如果文件内容不是有效的JSON，则重置它
                base_structure = {"data": []}
                with open(self.json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(base_structure, f, indent=4, ensure_ascii=False)

    def _load_json(self):
        """
        加载JSON文件数据

        Returns:
            dict: 解析后的JSON数据
        """
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            print(f"加载JSON文件失败: {e}")
            return {"data": []}

    def _save_json(self):
        """
        将数据保存回JSON文件
        """
        try:
            with open(self.json_file_path, 'w', encoding='utf-8') as file:
                json.dump(self.data, file, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存JSON文件失败: {e}")
            return False

    def _delete_file_or_dir(self, path):
        """
        删除文件或文件夹

        Args:
            path (str): 要删除的路径
        """
        if not path or not os.path.exists(path):
            return True

        try:
            if os.path.isfile(path):
                os.remove(path)
                print(f"文件已删除: {path}")
            elif os.path.isdir(path):
                shutil.rmtree(path)
                print(f"文件夹已删除: {path}")
            return True
        except Exception as e:
            print(f"删除路径失败 {path}: {e}")
            return False

    def add_data(self, new_items):
        """
        向JSON文件添加新数据

        Args:
            new_items (list or dict): 要添加的数据项或数据项列表

        Returns:
            bool: 操作是否成功
        """
        # 确保data键存在
        if 'data' not in self.data:
            self.data['data'] = []

        # 处理单个字典或列表
        if isinstance(new_items, dict):
            self.data['data'].append(new_items)
        elif isinstance(new_items, list):
            self.data['data'].extend(new_items)

        return self._save_json()

    def delete_data(self, condition):
        """
        根据条件删除数据，并同步删除对应的文件和文件夹

        Args:
            condition (function): 条件函数，接受数据项返回布尔值

        Returns:
            bool: 操作是否成功
        """
        if 'data' not in self.data:
            return False

        items_to_delete = [item for item in self.data['data'] if condition(item)]

        # 删除对应的文件和文件夹
        for item in items_to_delete:
            paths_to_delete = [
                item.get('pdf_path'),
                item.get('video_path'),
                item.get('output_dir')
            ]

            for path in paths_to_delete:
                self._delete_file_or_dir(path)

        # 从数据中删除项
        self.data['data'] = [item for item in self.data['data'] if not condition(item)]
        return self._save_json()

    def update_data(self, condition, update_fields):
        """
        根据条件更新数据

        Args:
            condition (function): 条件函数
            update_fields (dict): 要更新的字段和值

        Returns:
            bool: 操作是否成功
        """
        if 'data' not in self.data:
            return False

        updated = False
        for item in self.data['data']:
            if condition(item):
                item.update(update_fields)
                updated = True

        if updated:
            return self._save_json()
        return False

    def query_data(self, condition=None):
        """
        根据条件查询数据

        Args:
            condition (function, optional): 条件函数，如果为None则返回所有数据

        Returns:
            list: 匹配的数据项列表
        """
        if 'data' not in self.data:
            return []

        if condition is None:
            return self.data['data']

        return [item for item in self.data['data'] if condition(item)]

    def get_all_data(self):
        """
        获取所有数据

        Returns:
            list: 所有数据项
        """
        return self.data.get('data', [])

    def clear_all_data(self):
        """
        清空所有数据

        Returns:
            bool: 操作是否成功
        """
        # 先删除所有文件
        for item in self.data.get('data', []):
            paths_to_delete = [
                item.get('pdf_path'),
                item.get('video_path'),
                item.get('output_dir')
            ]

            for path in paths_to_delete:
                self._delete_file_or_dir(path)

        # 再清空数据
        self.data['data'] = []
        return self._save_json()