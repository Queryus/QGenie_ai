# src/core/monitoring/connection_monitor.py

import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ConnectionMonitor:
    """백엔드 연결 상태를 모니터링하는 클래스"""
    
    def __init__(self):
        self._last_connection_status: Optional[bool] = None  # 이전 연결 상태
        self._initial_connection_failed: bool = False  # 초기 연결 실패 여부
        self._connection_recovered: bool = False  # 연결 복구 완료 여부
        self._monitoring_enabled: bool = False  # 모니터링 활성화 여부
        self._monitoring_task: Optional[asyncio.Task] = None  # 모니터링 태스크
        self._monitoring_interval: int = 60  # 모니터링 간격 (초)
        self._last_success_time: Optional[datetime] = None  # 마지막 성공 시간
        
    def mark_initial_failure(self):
        """초기 연결 실패를 표시"""
        self._initial_connection_failed = True
        self._last_connection_status = False
        logger.info("🔄 ConnectionMonitor: 초기 연결 실패 상태로 설정됨")
    
    def mark_initial_success(self):
        """초기 연결 성공을 표시"""
        self._initial_connection_failed = False
        self._last_connection_status = True
        self._last_success_time = datetime.now()
        logger.info("✅ ConnectionMonitor: 초기 연결 성공 상태로 설정됨")
    
    async def check_api_call_recovery(self, operation_name: str = "API 호출") -> bool:
        """
        API 호출 성공 시 연결 복구 여부를 확인하고 로그를 출력합니다.
        
        Args:
            operation_name: 수행된 작업 이름
            
        Returns:
            bool: 연결이 복구되었는지 여부
        """
        current_time = datetime.now()
        
        # 이전에 연결이 실패했고, 아직 복구 로그를 출력하지 않은 경우
        if (self._initial_connection_failed or self._last_connection_status is False) and not self._connection_recovered:
            self._connection_recovered = True
            self._last_connection_status = True
            self._last_success_time = current_time
            
            # 복구 시간 계산
            if hasattr(self, '_failure_start_time'):
                downtime = current_time - self._failure_start_time
                logger.info(f"🎉 백엔드 서버 연결이 복구되었습니다! (다운타임: {downtime}) - {operation_name} 성공")
            else:
                logger.info(f"🎉 백엔드 서버 연결이 복구되었습니다! - {operation_name} 성공")
            
            # 연결이 복구되면 모니터링 중지
            if self._monitoring_enabled:
                logger.info("✅ 연결이 복구되어 백그라운드 모니터링을 중지합니다.")
                await self.stop_monitoring()
            
            return True
        
        # 정상 상태에서의 성공적인 호출
        self._last_success_time = current_time
        self._last_connection_status = True
        return False
    
    def mark_api_call_failure(self, operation_name: str = "API 호출"):
        """
        API 호출 실패 시 연결 상태를 업데이트합니다.
        
        Args:
            operation_name: 실패한 작업 이름
        """
        current_time = datetime.now()
        
        # 이전에 연결이 성공했던 경우에만 실패 로그 출력
        if self._last_connection_status is True:
            logger.warning(f"⚠️ 백엔드 서버 연결 실패 감지 - {operation_name} 실패")
            self._failure_start_time = current_time
        
        self._last_connection_status = False
        self._connection_recovered = False
    
    async def start_monitoring(self, api_client, interval: int = 60):
        """
        주기적인 연결 상태 모니터링을 시작합니다.
        
        Args:
            api_client: APIClient 인스턴스
            interval: 모니터링 간격 (초)
        """
        if self._monitoring_enabled:
            logger.warning("ConnectionMonitor: 모니터링이 이미 실행 중입니다")
            return
        
        self._monitoring_enabled = True
        self._monitoring_interval = interval
        
        logger.info(f"🔍 ConnectionMonitor: 백엔드 연결 모니터링 시작 (간격: {interval}초)")
        
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(api_client)
        )
    
    async def stop_monitoring(self):
        """연결 상태 모니터링을 중지합니다."""
        if not self._monitoring_enabled:
            return
        
        self._monitoring_enabled = False
        
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 ConnectionMonitor: 백엔드 연결 모니터링 중지")
    
    async def _monitoring_loop(self, api_client):
        """모니터링 루프 실행"""
        consecutive_failures = 0
        
        while self._monitoring_enabled:
            try:
                # 헬스체크 수행
                current_status = await api_client.health_check()
                current_time = datetime.now()
                
                # 상태 변화 감지
                if self._last_connection_status is not None:
                    if not self._last_connection_status and current_status:
                        # 연결 실패 → 성공으로 변화
                        if hasattr(self, '_failure_start_time'):
                            downtime = current_time - self._failure_start_time
                            logger.info(f"🎉 백엔드 서버 연결이 복구되었습니다! (다운타임: {downtime}) - 헬스체크 성공")
                        else:
                            logger.info("🎉 백엔드 서버 연결이 복구되었습니다! - 헬스체크 성공")
                        
                        self._connection_recovered = True
                        consecutive_failures = 0
                        
                        # 연결이 복구되면 모니터링 중지
                        logger.info("✅ 연결이 복구되어 백그라운드 모니터링을 중지합니다.")
                        self._monitoring_enabled = False
                        break
                        
                    elif self._last_connection_status and not current_status:
                        # 연결 성공 → 실패로 변화
                        logger.warning("⚠️ 백엔드 서버 연결이 끊어졌습니다! - 헬스체크 실패")
                        self._failure_start_time = current_time
                        self._connection_recovered = False
                        consecutive_failures = 1
                
                # 연결 상태 업데이트
                if current_status:
                    self._last_success_time = current_time
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                
                self._last_connection_status = current_status
                
                # 연속 실패 시 경고
                if consecutive_failures >= 3:
                    logger.error(f"🚨 백엔드 서버 연결이 {consecutive_failures * self._monitoring_interval}초 동안 실패 중입니다")
                
                # 모니터링 간격만큼 대기
                await asyncio.sleep(self._monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"ConnectionMonitor: 모니터링 중 오류 발생: {e}")
                await asyncio.sleep(self._monitoring_interval)
    
    def get_status(self) -> dict:
        """현재 연결 상태 정보를 반환합니다."""
        return {
            "last_connection_status": self._last_connection_status,
            "initial_connection_failed": self._initial_connection_failed,
            "connection_recovered": self._connection_recovered,
            "monitoring_enabled": self._monitoring_enabled,
            "last_success_time": self._last_success_time.isoformat() if self._last_success_time else None,
            "monitoring_interval": self._monitoring_interval
        }

# 싱글톤 인스턴스
_connection_monitor = ConnectionMonitor()

def get_connection_monitor() -> ConnectionMonitor:
    """ConnectionMonitor 싱글톤 인스턴스를 반환합니다."""
    return _connection_monitor
