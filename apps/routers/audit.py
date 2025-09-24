from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models import AuditLog
from datetime import datetime, date, timedelta
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def get_audit_logs(
    since: str = Query(default=None, description="Filter logs since date (YYYY-MM-DD)"),
    action: str = Query(default=None, description="Filter by action type"),
    result: str = Query(default=None, description="Filter by result: success, error, dry_run"),
    user: str = Query(default=None, description="Filter by user"),
    limit: int = Query(default=100, description="Maximum logs to return"),
    offset: int = Query(default=0, description="Pagination offset"),
    db: Session = Depends(get_db)
):
    """Get audit logs with optional filtering."""
    try:
        query = db.query(AuditLog)
        
        # Apply filters
        if since:
            try:
                since_date = datetime.strptime(since, "%Y-%m-%d")
                query = query.filter(AuditLog.timestamp >= since_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if result:
            query = query.filter(AuditLog.result == result)
        
        if user:
            query = query.filter(AuditLog.user == user)
        
        # Get total count for pagination
        total = query.count()
        
        # Apply pagination and ordering
        logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
        
        # Format results
        result_logs = []
        for log in logs:
            log_dict = {
                "id": log.id,
                "action": log.action,
                "user": log.user,
                "timestamp": log.timestamp.isoformat(),
                "result": log.result,
                "validate_only": log.validate_only,
                "customer_id": log.customer_id,
                "google_change_id": log.google_change_id,
                "error_message": log.error_message,
                "payload": json.loads(log.payload_json) if log.payload_json else {}
            }
            result_logs.append(log_dict)
        
        return {
            "logs": result_logs,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(logs) < total
            },
            "filters_applied": {
                "since": since,
                "action": action,
                "result": result,
                "user": user
            }
        }
        
    except Exception as e:
        logger.error(f"Getting audit logs failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get audit logs: {str(e)}")


@router.get("/summary")
def get_audit_summary(
    days: int = Query(default=30, description="Number of days to summarize"),
    db: Session = Depends(get_db)
):
    """Get summary statistics for audit logs."""
    try:
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Overall counts
        total_actions = db.query(AuditLog).filter(AuditLog.timestamp >= since_date).count()
        
        # By result
        result_stats = db.query(
            AuditLog.result,
            db.func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= since_date
        ).group_by(AuditLog.result).all()
        
        # By action type
        action_stats = db.query(
            AuditLog.action,
            db.func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= since_date
        ).group_by(AuditLog.action).all()
        
        # By validate_only flag
        validation_stats = db.query(
            AuditLog.validate_only,
            db.func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= since_date
        ).group_by(AuditLog.validate_only).all()
        
        # By user
        user_stats = db.query(
            AuditLog.user,
            db.func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= since_date
        ).group_by(AuditLog.user).all()
        
        # Recent errors
        recent_errors = db.query(AuditLog).filter(
            AuditLog.timestamp >= since_date,
            AuditLog.result == "error"
        ).order_by(AuditLog.timestamp.desc()).limit(5).all()
        
        return {
            "summary_period_days": days,
            "total_actions": total_actions,
            "breakdown": {
                "by_result": {stat.result: stat.count for stat in result_stats},
                "by_action": {stat.action: stat.count for stat in action_stats},
                "by_validation": {
                    "dry_run": sum(stat.count for stat in validation_stats if stat.validate_only),
                    "live": sum(stat.count for stat in validation_stats if not stat.validate_only)
                },
                "by_user": {stat.user: stat.count for stat in user_stats}
            },
            "recent_errors": [
                {
                    "id": err.id,
                    "action": err.action,
                    "timestamp": err.timestamp.isoformat(),
                    "error_message": err.error_message,
                    "user": err.user
                }
                for err in recent_errors
            ]
        }
        
    except Exception as e:
        logger.error(f"Getting audit summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get audit summary: {str(e)}")


@router.get("/{audit_id}")
def get_audit_log_detail(
    audit_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific audit log entry."""
    try:
        log = db.query(AuditLog).filter(AuditLog.id == audit_id).first()
        
        if not log:
            raise HTTPException(status_code=404, detail="Audit log not found")
        
        return {
            "id": log.id,
            "action": log.action,
            "user": log.user,
            "timestamp": log.timestamp.isoformat(),
            "result": log.result,
            "validate_only": log.validate_only,
            "customer_id": log.customer_id,
            "google_change_id": log.google_change_id,
            "error_message": log.error_message,
            "payload": json.loads(log.payload_json) if log.payload_json else {},
            "metadata": {
                "payload_size_bytes": len(log.payload_json) if log.payload_json else 0,
                "has_error": bool(log.error_message),
                "is_dry_run": log.validate_only,
                "google_resource_created": bool(log.google_change_id)
            }
        }
        
    except Exception as e:
        logger.error(f"Getting audit log detail failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get audit log detail: {str(e)}")


@router.get("/actions/available")
def get_available_actions(db: Session = Depends(get_db)):
    """Get list of available actions for filtering."""
    try:
        actions = db.query(AuditLog.action).distinct().all()
        results = db.query(AuditLog.result).distinct().all()
        users = db.query(AuditLog.user).distinct().all()
        
        return {
            "actions": [action[0] for action in actions if action[0]],
            "results": [result[0] for result in results if result[0]],
            "users": [user[0] for user in users if user[0]],
            "common_filters": {
                "last_24_hours": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),
                "last_7_days": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d"),
                "last_30_days": (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
            }
        }
        
    except Exception as e:
        logger.error(f"Getting available actions failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get available actions: {str(e)}")


@router.post("/export")
def export_audit_logs(
    since: str = Query(default=None, description="Export logs since date (YYYY-MM-DD)"),
    action: str = Query(default=None, description="Filter by action type"),
    result: str = Query(default=None, description="Filter by result"),
    format: str = Query(default="json", description="Export format: json or csv"),
    db: Session = Depends(get_db)
):
    """Export audit logs in various formats."""
    try:
        if format not in ["json", "csv"]:
            raise HTTPException(status_code=400, detail="Format must be 'json' or 'csv'")
        
        query = db.query(AuditLog)
        
        # Apply filters
        if since:
            try:
                since_date = datetime.strptime(since, "%Y-%m-%d")
                query = query.filter(AuditLog.timestamp >= since_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if result:
            query = query.filter(AuditLog.result == result)
        
        # Limit export size
        logs = query.order_by(AuditLog.timestamp.desc()).limit(10000).all()
        
        if format == "json":
            export_data = []
            for log in logs:
                log_dict = {
                    "id": log.id,
                    "action": log.action,
                    "user": log.user,
                    "timestamp": log.timestamp.isoformat(),
                    "result": log.result,
                    "validate_only": log.validate_only,
                    "customer_id": log.customer_id,
                    "google_change_id": log.google_change_id,
                    "error_message": log.error_message,
                    "payload": json.loads(log.payload_json) if log.payload_json else {}
                }
                export_data.append(log_dict)
            
            return {
                "format": "json",
                "total_records": len(export_data),
                "data": export_data,
                "export_timestamp": datetime.utcnow().isoformat(),
                "filters": {
                    "since": since,
                    "action": action,
                    "result": result
                }
            }
        
        else:  # CSV format
            # For CSV, we'll return a simplified structure
            csv_data = []
            for log in logs:
                csv_row = {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat(),
                    "action": log.action,
                    "user": log.user,
                    "result": log.result,
                    "validate_only": log.validate_only,
                    "customer_id": log.customer_id,
                    "google_change_id": log.google_change_id or "",
                    "error_message": log.error_message or "",
                    "payload_summary": json.loads(log.payload_json).get("reason", "") if log.payload_json else ""
                }
                csv_data.append(csv_row)
            
            return {
                "format": "csv",
                "total_records": len(csv_data),
                "headers": list(csv_data[0].keys()) if csv_data else [],
                "data": csv_data,
                "export_timestamp": datetime.utcnow().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Exporting audit logs failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
