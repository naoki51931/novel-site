
@router.get("/tags", response_model=list[schemas.TagRead])
def list_tags(db: Session = Depends(get_db)):
    return db.query(models.Tag).order_by(models.Tag.name.asc()).all()
