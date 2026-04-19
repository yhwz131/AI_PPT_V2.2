import logging
from datetime import datetime, time
from typing import Optional, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class TaskScheduler:
    """定时任务调度器"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.configure(timezone="Asia/Shanghai")  # 设置为中国时区
        self.jobs = {}

    def add_daily_job(
            self,
            job_id: str,
            func: Callable,
            hour: int = 8,
            minute: int = 0,
            **kwargs
    ) -> bool:
        """
        添加每日定时任务

        参数:
            job_id: 任务ID
            func: 要执行的函数
            hour: 小时 (0-23)
            minute: 分钟 (0-59)
            **kwargs: 传递给函数的参数
        """
        try:
            # 添加cron任务，每天指定时间执行
            trigger = CronTrigger(hour=hour, minute=minute, timezone="Asia/Shanghai")
            job = self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name=f"daily_{job_id}",
                kwargs=kwargs,
                replace_existing=True
            )

            self.jobs[job_id] = job

            # 尝试获取下一次执行时间
            next_run = None
            try:
                # 注意：在任务被正确调度前，next_run_time 可能为 None
                if hasattr(job, 'next_run_time') and job.next_run_time:
                    next_run = job.next_run_time
                    logger.info(f"添加定时任务 '{job_id}'，每天 {hour:02d}:{minute:02d} 执行，下次执行时间: {next_run}")
                else:
                    # 如果任务还没有被调度，可以尝试从调度器获取
                    scheduled_job = self.scheduler.get_job(job_id)
                    if scheduled_job and scheduled_job.next_run_time:
                        next_run = scheduled_job.next_run_time
                        logger.info(
                            f"添加定时任务 '{job_id}'，每天 {hour:02d}:{minute:02d} 执行，下次执行时间: {next_run}")
                    else:
                        # 如果仍然无法获取，就只记录任务已添加
                        logger.info(f"添加定时任务 '{job_id}'，每天 {hour:02d}:{minute:02d} 执行，等待调度器调度...")
            except AttributeError as e:
                # 如果访问属性出错，记录警告但不中断执行
                logger.warning(f"获取任务 '{job_id}' 的下次执行时间失败: {e}")
                logger.info(f"添加定时任务 '{job_id}'，每天 {hour:02d}:{minute:02d} 执行")

            return True

        except Exception as e:
            logger.error(f"添加定时任务 '{job_id}' 失败: {e}", exc_info=True)
            return False

    def add_interval_job(
            self,
            job_id: str,
            func: Callable,
            hours: int = 0,
            minutes: int = 0,
            seconds: int = 0,
            **kwargs
    ) -> bool:
        """
        添加间隔定时任务

        参数:
            job_id: 任务ID
            func: 要执行的函数
            hours: 小时间隔
            minutes: 分钟间隔
            seconds: 秒间隔
            **kwargs: 传递给函数的参数
        """
        try:
            job = self.scheduler.add_job(
                func=func,
                trigger='interval',
                hours=hours,
                minutes=minutes,
                seconds=seconds,
                id=job_id,
                name=f"interval_{job_id}",
                kwargs=kwargs,
                replace_existing=True,
                timezone="Asia/Shanghai"
            )

            self.jobs[job_id] = job

            # 尝试获取下一次执行时间
            next_run = None
            try:
                if hasattr(job, 'next_run_time') and job.next_run_time:
                    next_run = job.next_run_time
                    logger.info(
                        f"添加间隔任务 '{job_id}'，间隔: {hours}小时 {minutes}分钟 {seconds}秒，下次执行时间: {next_run}")
                else:
                    # 如果任务还没有被调度，可以尝试从调度器获取
                    scheduled_job = self.scheduler.get_job(job_id)
                    if scheduled_job and scheduled_job.next_run_time:
                        next_run = scheduled_job.next_run_time
                        logger.info(
                            f"添加间隔任务 '{job_id}'，间隔: {hours}小时 {minutes}分钟 {seconds}秒，下次执行时间: {next_run}")
                    else:
                        logger.info(
                            f"添加间隔任务 '{job_id}'，间隔: {hours}小时 {minutes}分钟 {seconds}秒，等待调度器调度...")
            except AttributeError as e:
                logger.warning(f"获取任务 '{job_id}' 的下次执行时间失败: {e}")
                logger.info(f"添加间隔任务 '{job_id}'，间隔: {hours}小时 {minutes}分钟 {seconds}秒")

            return True

        except Exception as e:
            logger.error(f"添加间隔任务 '{job_id}' 失败: {e}", exc_info=True)
            return False

    def start(self) -> bool:
        """启动调度器"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("定时任务调度器已启动")

                # 调度器启动后，可以重新获取所有任务的下次执行时间
                self.log_all_jobs_next_run()

                return True
            else:
                logger.warning("定时任务调度器已经在运行")
                return False
        except Exception as e:
            logger.error(f"启动定时任务调度器失败: {e}", exc_info=True)
            return False

    def log_all_jobs_next_run(self):
        """记录所有任务的下次执行时间（调度器启动后调用）"""
        try:
            if not self.jobs:
                logger.info("当前没有定时任务")
                return

            logger.info("当前定时任务状态:")
            for job_id, job in self.jobs.items():
                try:
                    # 再次从调度器获取任务，确保获取最新的状态
                    scheduled_job = self.scheduler.get_job(job_id)
                    if scheduled_job and scheduled_job.next_run_time:
                        logger.info(f"  任务 '{job_id}': 下次执行时间: {scheduled_job.next_run_time}")
                    else:
                        logger.info(f"  任务 '{job_id}': 未调度或已暂停")
                except Exception as e:
                    logger.warning(f"获取任务 '{job_id}' 状态失败: {e}")
        except Exception as e:
            logger.error(f"记录任务状态失败: {e}")

    def shutdown(self) -> bool:
        """关闭调度器"""
        try:
            if self.scheduler.running:
                logger.info("正在关闭定时任务调度器...")
                self.scheduler.shutdown(wait=True)  # wait=True 等待所有任务完成
                logger.info("定时任务调度器已关闭")
                return True
            else:
                logger.warning("定时任务调度器未运行")
                return False
        except Exception as e:
            logger.error(f"关闭定时任务调度器失败: {e}", exc_info=True)
            return False

    def remove_job(self, job_id: str) -> bool:
        """移除指定任务"""
        try:
            if job_id in self.jobs:
                success = self.scheduler.remove_job(job_id)
                if success:
                    del self.jobs[job_id]
                    logger.info(f"已移除定时任务: {job_id}")
                    return True
                else:
                    logger.warning(f"调度器移除任务失败: {job_id}")
                    return False
            else:
                logger.warning(f"定时任务不存在: {job_id}")
                return False
        except Exception as e:
            logger.error(f"移除定时任务失败 {job_id}: {e}", exc_info=True)
            return False

    def get_job_info(self, job_id: str) -> Optional[dict]:
        """获取任务信息"""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            try:
                return {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger)
                }
            except AttributeError:
                # 如果获取属性失败，尝试从调度器获取
                scheduled_job = self.scheduler.get_job(job_id)
                if scheduled_job:
                    return {
                        'id': scheduled_job.id,
                        'name': scheduled_job.name,
                        'next_run_time': scheduled_job.next_run_time.isoformat() if scheduled_job.next_run_time else None,
                        'trigger': str(scheduled_job.trigger)
                    }
        return None

    def list_jobs(self) -> list:
        """获取所有任务列表"""
        jobs_info = []
        for job_id in list(self.jobs.keys()):
            job_info = self.get_job_info(job_id)
            if job_info:
                jobs_info.append(job_info)

        # 也可以直接从调度器获取所有任务
        scheduler_jobs = self.scheduler.get_jobs()
        for job in scheduler_jobs:
            # 避免重复
            if not any(j['id'] == job.id for j in jobs_info):
                jobs_info.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger)
                })

        return jobs_info

    def pause_job(self, job_id: str) -> bool:
        """暂停任务"""
        try:
            if job_id in self.jobs:
                self.scheduler.pause_job(job_id)
                logger.info(f"已暂停定时任务: {job_id}")
                return True
            else:
                logger.warning(f"定时任务不存在: {job_id}")
                return False
        except Exception as e:
            logger.error(f"暂停定时任务失败 {job_id}: {e}", exc_info=True)
            return False

    def resume_job(self, job_id: str) -> bool:
        """恢复任务"""
        try:
            if job_id in self.jobs:
                self.scheduler.resume_job(job_id)
                logger.info(f"已恢复定时任务: {job_id}")
                return True
            else:
                logger.warning(f"定时任务不存在: {job_id}")
                return False
        except Exception as e:
            logger.error(f"恢复定时任务失败 {job_id}: {e}", exc_info=True)
            return False

    def get_scheduler_status(self) -> dict:
        """获取调度器状态"""
        try:
            return {
                'running': self.scheduler.running,
                'job_count': len(self.jobs),
                'scheduled_job_count': len(self.scheduler.get_jobs()),
                'timezone': str(self.scheduler.timezone) if hasattr(self.scheduler, 'timezone') else '未知'
            }
        except Exception as e:
            logger.error(f"获取调度器状态失败: {e}")
            return {
                'running': False,
                'job_count': len(self.jobs),
                'error': str(e)
            }